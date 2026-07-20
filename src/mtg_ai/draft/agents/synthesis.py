"""Synthesis agent: the final judgement.

Strong-tier (Sonnet/Opus). Weighs raw power (from evaluation) against deck fit (from
archetype) and signal, and produces the recommended pick, ranked alternatives, and a short
rationale. This is the one step where the stronger model is justified.
"""

from __future__ import annotations

from ...core.llm import LLM
from ...core.models import CostEntry
from ..models import (
    ArchetypeRead,
    EnrichedDraftState,
    EvaluationResult,
    PickRecommendation,
)

SYSTEM = (
    "You are the synthesis agent in an MTG Arena draft assistant. You receive the drafter's "
    "archetype read and a deck-agnostic evaluation of the current pack. Recommend the single "
    "best pick, weighing raw power against deck fit and draft signal. Prefer on-color, "
    "synergistic cards unless an off-color card is clearly stronger. Give 2-3 ranked "
    "alternatives and a 2-3 sentence rationale a drafter can act on."
)


class SynthesisAgent:
    name = "synthesis"

    def __init__(self, llm: LLM, model: str) -> None:
        self._llm = llm
        self._model = model

    def run(
        self,
        enriched: EnrichedDraftState,
        archetype: ArchetypeRead,
        evaluation: EvaluationResult,
    ) -> tuple[PickRecommendation, CostEntry]:
        user = (
            f"Archetype read: {archetype.summary} "
            f"(committed {[c.value for c in archetype.committed_colors]}).\n"
            f"Pack evaluation (best first): "
            + ", ".join(f"{s.name} [p{s.power_score}/s{s.signal_score}]" for s in evaluation.ranked)
            + "\n\nRecommend the pick."
        )
        return self._llm.structured(
            agent=self.name,
            model=self._model,
            system=SYSTEM,
            user=user,
            context={"archetype": archetype, "evaluation": evaluation, "pack": enriched.pack},
            response_model=PickRecommendation,
        )
