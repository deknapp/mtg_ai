"""Stage 1 data-layer tests: Scryfall mapping + SQLite repository, on a small fixture."""

from __future__ import annotations

from mtg_ai.core.data import SqliteCardRepository, build_sqlite, card_from_scryfall
from mtg_ai.core.models import Color

# A few representative Scryfall bulk records: mono-color, colorless land, and a double-faced card.
FIXTURE = [
    {
        "name": "Murder",
        "mana_cost": "{1}{B}{B}",
        "cmc": 3.0,
        "colors": ["B"],
        "type_line": "Instant",
        "oracle_text": "Destroy target creature.",
        "rarity": "uncommon",
    },
    {
        "name": "Evolving Wilds",
        "mana_cost": "",
        "cmc": 0.0,
        "colors": [],
        "type_line": "Land",
        "oracle_text": "{T}, Sacrifice this land: Search your library for a basic land card...",
        "rarity": "common",
    },
    {
        "name": "Brutal Cathar // Moonrage Brute",
        "cmc": 3.0,
        "type_line": "Creature — Human Cleric // Creature — Werewolf Horror",
        "rarity": "rare",
        "card_faces": [
            {"name": "Brutal Cathar", "mana_cost": "{2}{W}", "colors": ["W"],
             "type_line": "Creature — Human Cleric", "oracle_text": "When this enters...",
             "power": "2", "toughness": "2"},
            {"name": "Moonrage Brute", "colors": ["R"],
             "type_line": "Creature — Werewolf Horror", "oracle_text": "Trample.",
             "power": "4", "toughness": "4"},
        ],
    },
    {"cmc": 1.0, "type_line": "Token"},  # unusable: no name -> dropped
]


def test_scryfall_mapping_basic():
    card = card_from_scryfall(FIXTURE[0])
    assert card is not None
    assert card.colors == [Color.BLACK]
    assert card.cmc == 3.0
    assert card.type_line == "Instant"


def test_scryfall_mapping_double_faced_uses_first_face():
    card = card_from_scryfall(FIXTURE[2])
    assert card is not None
    assert card.mana_cost == "{2}{W}"          # pulled from the front face
    assert card.power == "2"
    assert Color.WHITE in card.colors and Color.RED in card.colors  # union across faces


def test_unusable_record_dropped():
    assert card_from_scryfall(FIXTURE[3]) is None


def test_build_and_lookup_sqlite(tmp_path):
    db = tmp_path / "cards.sqlite"
    written = build_sqlite(db, FIXTURE)
    assert written == 3  # the nameless token is skipped

    repo = SqliteCardRepository(db)
    assert repo.lookup("Murder").rarity == "uncommon"
    assert repo.lookup("murder") is not None      # case-insensitive
    assert repo.lookup("Evolving Wilds").colors == []
    assert repo.lookup("Nonexistent Card") is None
