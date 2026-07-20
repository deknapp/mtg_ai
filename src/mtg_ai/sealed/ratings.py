"""17Lands card-ratings: fetch, cache, and a PER-CARD cross-format fallback.

The live 17Lands `card_ratings/data` endpoint publishes a card's games-in-hand win rate (GIHWR)
only once it has enough sample. For a fresh set that means commons/uncommons get numbers first
and rares/mythics lag (and Sealed lags Draft because far fewer people play it). So instead of
picking one format wholesale, we build a **per-card** index: for each card, take the win rate
from the best format that actually has one, preferring the player's real event (ArenaDirect
Sealed) and only then falling back to generic Sealed and finally Draft — tagging each number
with its source format and game count so a sealed number and a draft-proxy are never confused.

Cards with no win rate in any format (typically bombs on a new set) get no rating — the builder
flags them and the AI judges them from the card. Nothing is faked.

Note on completeness: this endpoint serves a rolling view, not the full historical dataset (that
lives in 17Lands' S3 public datasets, which aren't published for every set yet). `SOURCE_LADDER`
is ordered so an S3-backed all-time source can be slotted in at the top later without changes
elsewhere. Reload with the app's reload action to pick up new data as it accrues.
"""

from __future__ import annotations

import json
import sqlite3
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

CARD_RATINGS_URL = "https://www.17lands.com/card_ratings/data"
UA = "mtg_ai/0.1 (personal sealed deck builder)"

# API column -> our column.
FIELD_MAP = {
    "name": "name", "mtga_id": "mtga_id", "rarity": "rarity", "color": "color",
    "game_count": "game_count", "ever_drawn_win_rate": "gih_wr",
    "drawn_improvement_win_rate": "iwd",
}

# Per-card fallback order for a sealed pool, best-first. The player's actual event
# (ArenaDirect_Sealed) wins; generic Sealed next; Draft is the last-resort power proxy (card
# quality transfers across 40-card limited, though sealed win-rates run a few points higher).
SEALED_LADDER = ["ArenaDirect_Sealed", "Sealed", "TradSealed", "PremierDraft", "TradDraft"]


@dataclass
class Rating:
    wr: float
    source: str   # the 17Lands format this number came from
    games: int    # game_count backing it, i.e. confidence


@dataclass
class RatingsIndex:
    """Per-card best-available win rate for a set, plus which formats contributed."""

    set_code: str
    by_id: dict[int, Rating] = field(default_factory=dict)
    formats_present: list[str] = field(default_factory=list)

    def get(self, arena_id: int | None) -> Rating | None:
        return self.by_id.get(arena_id) if arena_id is not None else None


class RatingsCache:
    def __init__(self, db_path: str | Path) -> None:
        self.db_path = str(Path(db_path).expanduser())
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self.db_path) as con:
            con.execute(
                """CREATE TABLE IF NOT EXISTS card_ratings (
                    set_code TEXT, format TEXT, name TEXT, mtga_id INTEGER,
                    rarity TEXT, color TEXT, game_count INTEGER, gih_wr REAL, iwd REAL,
                    fetched_at TEXT, PRIMARY KEY (set_code, format, name))"""
            )

    # --- network / cache -------------------------------------------------------
    @staticmethod
    def _fetch_raw(set_code: str, fmt: str) -> list[dict]:
        url = f"{CARD_RATINGS_URL}?expansion={set_code.upper()}&format={fmt}"
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310 (trusted host)
            return json.loads(resp.read().decode("utf-8"))

    def reload(self, set_code: str, fmt: str) -> int:
        raw = self._fetch_raw(set_code, fmt)
        rows = [{ours: r.get(api) for api, ours in FIELD_MAP.items()} for r in raw]
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        with sqlite3.connect(self.db_path) as con:
            con.execute("DELETE FROM card_ratings WHERE set_code=? AND format=?", (set_code, fmt))
            con.executemany(
                """INSERT OR REPLACE INTO card_ratings
                   (set_code, format, name, mtga_id, rarity, color, game_count, gih_wr, iwd, fetched_at)
                   VALUES (:set_code,:format,:name,:mtga_id,:rarity,:color,:game_count,:gih_wr,:iwd,:fetched_at)""",
                [{**r, "set_code": set_code, "format": fmt, "fetched_at": now} for r in rows],
            )
        return len(rows)

    def _read(self, set_code: str, fmt: str) -> list[dict]:
        with sqlite3.connect(self.db_path) as con:
            con.row_factory = sqlite3.Row
            cur = con.execute(
                "SELECT * FROM card_ratings WHERE set_code=? AND format=?", (set_code, fmt)
            )
            return [dict(r) for r in cur.fetchall()]

    def is_cached(self, set_code: str, fmt: str) -> bool:
        return bool(self._read(set_code, fmt))

    @staticmethod
    def _usable(rows: list[dict]) -> bool:
        return any(r.get("gih_wr") is not None for r in rows)

    # --- per-card index --------------------------------------------------------
    def build_index(self, set_code: str, ladder: list[str] = SEALED_LADDER) -> RatingsIndex:
        """Merge cached formats into one per-card best-available index (no network)."""
        idx = RatingsIndex(set_code=set_code)
        present: list[str] = []
        # Walk the ladder best-first; the first format to supply a card wins and isn't overwritten.
        for fmt in ladder:
            rows = self._read(set_code, fmt)
            if self._usable(rows):
                present.append(fmt)
            for r in rows:
                mid, wr = r.get("mtga_id"), r.get("gih_wr")
                if mid is None or wr is None or mid in idx.by_id:
                    continue
                idx.by_id[mid] = Rating(wr=wr, source=fmt, games=int(r.get("game_count") or 0))
        idx.formats_present = present
        return idx

    def ensure_index(self, set_code: str, ladder: list[str] = SEALED_LADDER, *,
                     reload: bool = False) -> RatingsIndex:
        """Guarantee the ladder's formats are cached (fetching as needed), then build the index."""
        for fmt in ladder:
            if reload or not self.is_cached(set_code, fmt):
                try:
                    self.reload(set_code, fmt)
                except Exception:  # noqa: BLE001 - offline / rate-limited: use whatever is cached
                    pass
        return self.build_index(set_code, ladder)
