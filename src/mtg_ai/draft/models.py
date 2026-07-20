"""Typed messages passed between the draft agents.

Every inter-agent interface is a Pydantic model, so the whole pipeline is inspectable and
testable. Shared primitives (`Card`, `Color`, `CostEntry`) come from `core.models`.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from ..core.models import Card, Color, CostEntry


# --- Extraction ----------------------------------------------------------------------------


class DraftState(BaseModel):
    """Raw output of the vision/extraction agent: card names only, no facts yet."""

    picked: list[str] = Field(default_factory=list, description="Names of cards already drafted.")
    pack: list[str] = Field(default_factory=list, description="Names of cards in the current pack.")


# --- Enrichment (deterministic, from the Scryfall data layer) -----------------------------


class EnrichedDraftState(BaseModel):
    """Draft state after every card name has been joined against the data layer."""

    picked: list[Card] = Field(default_factory=list)
    pack: list[Card] = Field(default_factory=list)


# --- Reasoning agents ----------------------------------------------------------------------


class ArchetypeRead(BaseModel):
    """The archetype/color agent's read of what the deck is becoming."""

    committed_colors: list[Color] = Field(default_factory=list)
    open_lanes: list[str] = Field(default_factory=list, description="Under-drafted directions.")
    curve_gaps: list[str] = Field(default_factory=list, description="Missing spots on the curve.")
    summary: str = ""


class CardScore(BaseModel):
    """The card-evaluation agent's judgement of one card in the pack."""

    name: str
    power_score: float = Field(ge=0, le=10, description="Raw card power, deck-agnostic.")
    signal_score: float = Field(ge=0, le=10, description="Limited-format / draft signal.")
    note: str = ""


class EvaluationResult(BaseModel):
    """Ranked evaluation of the whole pack, deck-agnostic."""

    ranked: list[CardScore] = Field(default_factory=list)


# --- Synthesis (final answer) --------------------------------------------------------------


class Alternative(BaseModel):
    name: str
    reason: str = ""


class PickRecommendation(BaseModel):
    """The synthesis agent's final answer, rendered by the UI."""

    pick: str
    alternatives: list[Alternative] = Field(default_factory=list)
    rationale: str = ""


class PipelineResult(BaseModel):
    """Everything produced for one pick: the recommendation plus every agent's intermediate output."""

    draft_state: DraftState
    enriched: EnrichedDraftState
    archetype: ArchetypeRead
    evaluation: EvaluationResult
    recommendation: PickRecommendation
    cost_log: list[CostEntry] = Field(default_factory=list)
