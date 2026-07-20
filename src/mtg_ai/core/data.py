"""Card data layer.

Enrichment joins card identifiers against a `CardRepository`. The interface is deliberately
thin so the in-memory stub can be swapped for a SQLite-backed Scryfall store without touching
the agents. Lookups are supported by name (draft: OCR'd from a screenshot) and by Arena id
(sealed: read straight from the Arena log), so each format resolves cards the way it gets them.
"""

from __future__ import annotations

import sqlite3
from abc import ABC, abstractmethod
from collections.abc import Iterable
from pathlib import Path

from .models import Card, Color


class CardRepository(ABC):
    """Lookup card facts by (case-insensitive) name or by Arena id."""

    @abstractmethod
    def lookup(self, name: str) -> Card | None:
        raise NotImplementedError

    @abstractmethod
    def all_names(self) -> list[str]:
        """Every card name in the store, used for fuzzy-matching OCR misreads."""
        raise NotImplementedError

    def lookup_by_arena_id(self, arena_id: int) -> Card | None:
        """Resolve a card by its Arena id (Scryfall `arena_id`). Optional; None if unsupported."""
        return None


# A tiny, hand-entered card table used for skeleton/mock runs so the pipeline has real-looking
# facts to reason over. Replaced by the Scryfall-backed store for real runs.
_STUB_CARDS: list[Card] = [
    Card(name="Lightning Strike", mana_cost="{1}{R}", cmc=2, colors=[Color.RED],
         type_line="Instant", oracle_text="Lightning Strike deals 3 damage to any target.",
         rarity="common", rating=6.5),
    Card(name="Goblin Guide", mana_cost="{R}", cmc=1, colors=[Color.RED],
         type_line="Creature — Goblin Scout", oracle_text="Haste. Attacks each combat if able.",
         rarity="rare", power="2", toughness="2", rating=6.0),
    Card(name="Duress", mana_cost="{B}", cmc=1, colors=[Color.BLACK],
         type_line="Sorcery", oracle_text="Target opponent reveals their hand; you choose a "
         "noncreature nonland card. That player discards it.", rarity="common", rating=4.5),
    Card(name="Murder", mana_cost="{1}{B}{B}", cmc=3, colors=[Color.BLACK],
         type_line="Instant", oracle_text="Destroy target creature.", rarity="uncommon",
         rating=7.5),
    Card(name="Shock", mana_cost="{R}", cmc=1, colors=[Color.RED],
         type_line="Instant", oracle_text="Shock deals 2 damage to any target.",
         rarity="common", rating=6.0),
    Card(name="Serra Angel", mana_cost="{3}{W}{W}", cmc=5, colors=[Color.WHITE],
         type_line="Creature — Angel", oracle_text="Flying, vigilance.", rarity="uncommon",
         power="4", toughness="4", rating=7.0),
    Card(name="Llanowar Elves", mana_cost="{G}", cmc=1, colors=[Color.GREEN],
         type_line="Creature — Elf Druid", oracle_text="{T}: Add {G}.", rarity="common",
         power="1", toughness="1", rating=5.5),
    Card(name="Divination", mana_cost="{2}{U}", cmc=3, colors=[Color.BLUE],
         type_line="Sorcery", oracle_text="Draw two cards.", rarity="common", rating=5.0),
]


class StubCardRepository(CardRepository):
    """In-memory repository over a small built-in table."""

    def __init__(self) -> None:
        self._by_name = {c.name.lower(): c for c in _STUB_CARDS}

    def lookup(self, name: str) -> Card | None:
        return self._by_name.get(name.strip().lower())

    def all_names(self) -> list[str]:
        return [c.name for c in _STUB_CARDS]


# --- Scryfall -> Card mapping --------------------------------------------------------------


def _first(raw: dict, key: str) -> object | None:
    """Read a field from a card, falling back to its first face (double-faced cards)."""
    if raw.get(key) is not None:
        return raw[key]
    faces = raw.get("card_faces")
    if faces:
        return faces[0].get(key)
    return None


def card_from_scryfall(raw: dict) -> Card | None:
    """Map one Scryfall bulk record to our `Card`. Returns None for unusable records."""
    name = raw.get("name")
    if not name:
        return None

    colors = raw.get("colors")
    if colors is None and raw.get("card_faces"):
        seen: list[str] = []
        for face in raw["card_faces"]:
            for c in face.get("colors", []):
                if c not in seen:
                    seen.append(c)
        colors = seen
    parsed_colors = [Color(c) for c in (colors or []) if c in Color._value2member_map_]

    oracle = raw.get("oracle_text")
    if oracle is None and raw.get("card_faces"):
        oracle = " // ".join(f.get("oracle_text", "") for f in raw["card_faces"]).strip(" /")

    arena_id = raw.get("arena_id")
    produced = [Color(c) for c in (raw.get("produced_mana") or []) if c in Color._value2member_map_]
    return Card(
        name=name,
        mana_cost=_first(raw, "mana_cost"),
        cmc=float(raw.get("cmc") or 0.0),
        colors=parsed_colors,
        produced_mana=produced,
        type_line=raw.get("type_line") or _first(raw, "type_line"),
        oracle_text=oracle,
        rarity=raw.get("rarity"),
        power=_first(raw, "power"),
        toughness=_first(raw, "toughness"),
        arena_id=int(arena_id) if arena_id is not None else None,
    )


# --- SQLite-backed repository --------------------------------------------------------------

_SCHEMA = (
    "CREATE TABLE IF NOT EXISTS cards ("
    "name TEXT PRIMARY KEY COLLATE NOCASE, arena_id INTEGER, data TEXT)"
)
_ARENA_INDEX = "CREATE INDEX IF NOT EXISTS idx_cards_arena ON cards(arena_id)"


def build_sqlite(db_path: str | Path, cards: Iterable[dict]) -> int:
    """Build the local card store from an iterable of Scryfall bulk records.

    Kept separate from the network fetch so it can be driven by a fixture in tests. Returns
    the number of cards written. Stores `arena_id` alongside so sealed pools (read from the
    Arena log as ids) resolve without name matching.
    """
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    try:
        conn.execute(_SCHEMA)
        conn.execute(_ARENA_INDEX)
        count = 0
        for raw in cards:
            card = card_from_scryfall(raw)
            if card is None:
                continue
            conn.execute(
                "INSERT OR REPLACE INTO cards (name, arena_id, data) VALUES (?, ?, ?)",
                (card.name, card.arena_id, card.model_dump_json()),
            )
            count += 1
        conn.commit()
        return count
    finally:
        conn.close()


class SqliteCardRepository(CardRepository):
    """Repository over the ingested Scryfall SQLite store. Same interface as the stub."""

    def __init__(self, db_path: str | Path) -> None:
        if not Path(db_path).exists():
            raise FileNotFoundError(
                f"Card database not found at {db_path!r}. Run `python -m "
                f"mtg_ai.core.ingest --set msh` to build it."
            )
        # check_same_thread=False so the async pipeline's worker threads can read.
        self._conn = sqlite3.connect(db_path, check_same_thread=False)

    def lookup(self, name: str) -> Card | None:
        row = self._conn.execute(
            "SELECT data FROM cards WHERE name = ? COLLATE NOCASE", (name.strip(),)
        ).fetchone()
        return Card.model_validate_json(row[0]) if row else None

    def lookup_by_arena_id(self, arena_id: int) -> Card | None:
        row = self._conn.execute(
            "SELECT data FROM cards WHERE arena_id = ?", (int(arena_id),)
        ).fetchone()
        return Card.model_validate_json(row[0]) if row else None

    def all_names(self) -> list[str]:
        return [r[0] for r in self._conn.execute("SELECT name FROM cards").fetchall()]
