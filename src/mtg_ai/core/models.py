"""Shared, format-agnostic domain models.

`Color`, `Card`, and `CostEntry` are used by every format (draft, sealed, ...). Format-specific
message types live under each format package's own `models` module.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class Color(str, Enum):
    """MTG's five-color mana identity (WUBRG)."""

    WHITE = "W"
    BLUE = "U"
    BLACK = "B"
    RED = "R"
    GREEN = "G"


class Card(BaseModel):
    """A card enriched with real facts from the Scryfall data layer."""

    name: str
    mana_cost: str | None = None
    cmc: float = 0.0
    colors: list[Color] = Field(default_factory=list)
    type_line: str | None = None
    oracle_text: str | None = None
    rarity: str | None = None
    power: str | None = None
    toughness: str | None = None
    # Arena's card id (Scryfall `arena_id`). Lets us join the Arena log + 17Lands by id, not name.
    arena_id: int | None = None
    # Optional limited-format signal (e.g. 17Lands GIH win-rate), filled in by enrichment.
    rating: float | None = None
    # True when the identifier could not be resolved against the data layer.
    unresolved: bool = False

    @property
    def is_land(self) -> bool:
        return bool(self.type_line and "Land" in self.type_line)

    @property
    def is_creature(self) -> bool:
        return bool(self.type_line and "Creature" in self.type_line)


class CostEntry(BaseModel):
    """One LLM call's cost accounting, for the per-run cost log."""

    agent: str
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    cached_input_tokens: int = 0
