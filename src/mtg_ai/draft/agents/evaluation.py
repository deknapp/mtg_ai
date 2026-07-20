"""Card Evaluation agent: ranks the current pack on raw power + limited signal.

Cheap-tier. Deck-agnostic on purpose — deck fit is the synthesis agent's job. Runs
independently of (and in parallel with) the archetype agent.
"""

from __future__ import annotations

from ...core.llm import LLM
from ...core.models import CostEntry
from ..models import EnrichedDraftState, EvaluationResult

SYSTEM = (
    "You are the card-evaluation agent in an MTG Arena draft assistant. Given the cards in the "
    "current pack, rank them by raw power and limited-format signal, independent of any "
    "particular deck. Score each 0-10 on power and on signal, with a one-line note."
)


class EvaluationAgent:
    name = "evaluation"

    def __init__(self, llm: LLM, model: str) -> None:
        self._llm = llm
        self._model = model

    def run(self, enriched: EnrichedDraftState) -> tuple[EvaluationResult, CostEntry]:
        pack_desc = "\n".join(
            f"- {c.name} ({c.type_line}, cmc {c.cmc:g}, {c.rarity or 'unknown'})"
            for c in enriched.pack
        )
        return self._llm.structured(
            agent=self.name,
            model=self._model,
            system=SYSTEM,
            user=f"Rank this pack:\n{pack_desc}",
            context={"pack": enriched.pack},
            response_model=EvaluationResult,
        )
