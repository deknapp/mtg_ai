"""Typed messages for the sealed pipeline. Shared primitives come from `core.models`."""

from __future__ import annotations

from pydantic import BaseModel, Field

from ..core.models import Card, Color, CostEntry


class Pool(BaseModel):
    """A sealed pool: the cards opened from six packs, resolved against the data layer."""

    set_code: str
    event: str | None = None
    cards: list[Card] = Field(default_factory=list)
    # Arena ids that could not be resolved against the card DB (should be empty for a set-scoped DB).
    unresolved_ids: list[int] = Field(default_factory=list)

    @property
    def spells(self) -> list[Card]:
        return [c for c in self.cards if not c.is_land]


class ColorPairScore(BaseModel):
    """Deterministic score for one of the ten two-color pairs over the pool."""

    label: str  # e.g. "WB"
    colors: list[Color]
    playable_count: int
    deck_score: float = Field(description="Sum of the best 23 castable spells' effective ratings.")
    avg_rating: float
    bomb_count: int
    removal_count: int
    creature_count: int
    note: str = ""


class DeckCard(BaseModel):
    """One nonland card in the built deck (with the facts the UI/rationale need)."""

    name: str
    cmc: float
    colors: list[Color] = Field(default_factory=list)
    rarity: str | None = None
    rating: float | None = None  # 17Lands GIH win-rate (or inferred baseline)
    is_bomb: bool = False
    role: str = "other"  # creature | removal | other


class Manabase(BaseModel):
    """The mana-feasibility result: land split + source counts + a Karsten-style check."""

    lands: dict[str, int] = Field(default_factory=dict)  # land name -> count
    sources: dict[str, int] = Field(default_factory=dict)  # color letter -> source count
    total_lands: int = 0
    feasible: bool = True
    notes: list[str] = Field(default_factory=list)


class SealedDeck(BaseModel):
    """The final 40-card build."""

    colors: list[Color]
    spells: list[DeckCard]
    manabase: Manabase
    curve: dict[str, int] = Field(default_factory=dict)  # "1".."6+" -> count
    bombs: list[str] = Field(default_factory=list)
    creatures: int = 0
    removal: int = 0
    total_cards: int = 0
    sideboard_highlights: list[DeckCard] = Field(default_factory=list)
    rationale: str = ""


class LLMBuild(BaseModel):
    """Structured output from the AI deckbuilder agent — its judgement over the pool.

    The AI picks colors (2 or 3) and the maindeck spells and reasons about synergies; the
    deterministic manabase optimizer then enforces castability on whatever it chose.
    """

    colors: list[Color] = Field(description="The 2 (or 3, if justified) colors to build.")
    maindeck: list[str] = Field(
        default_factory=list, description="~22-24 nonland card names from the pool to play."
    )
    bombs: list[str] = Field(default_factory=list, description="Bomb cards built around.")
    synergies: list[str] = Field(
        default_factory=list, description="Short notes on the synergies the build leans on."
    )
    rationale: str = ""


class SealedResult(BaseModel):
    """Everything produced for one sealed build: the deck plus every stage's intermediate output."""

    pool: Pool
    colorpair_scores: list[ColorPairScore] = Field(default_factory=list)
    chosen_colors: list[Color] = Field(default_factory=list)
    deck: SealedDeck
    cost_log: list[CostEntry] = Field(default_factory=list)
    built_by: str = "deterministic"  # "deterministic" | "ai"
    synergies: list[str] = Field(default_factory=list)
