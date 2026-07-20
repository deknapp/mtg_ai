"""Archetype/Color agent: reads what the deck is becoming.

Cheap-tier. Looks only at the already-picked pool: color commitment, open lanes, curve gaps.
Runs independently of (and in parallel with) the evaluation agent.
"""

from __future__ import annotations

from ...core.llm import LLM
from ...core.models import CostEntry
from ..models import ArchetypeRead, EnrichedDraftState

SYSTEM = (
    "You are the archetype agent in an MTG Arena draft assistant. Given the cards a drafter "
    "has already picked, assess what deck they are building: which colors they are committed "
    "to, which lanes look open, and where the mana curve has gaps. Be concise and concrete."
)


class ArchetypeAgent:
    name = "archetype"

    def __init__(self, llm: LLM, model: str) -> None:
        self._llm = llm
        self._model = model

    def run(self, enriched: EnrichedDraftState) -> tuple[ArchetypeRead, CostEntry]:
        picked_desc = "\n".join(
            f"- {c.name} ({''.join(x.value for x in c.colors) or 'C'}, {c.type_line})"
            for c in enriched.picked
        )
        return self._llm.structured(
            agent=self.name,
            model=self._model,
            system=SYSTEM,
            user=f"Already picked:\n{picked_desc}\n\nWhat is this deck becoming?",
            context={"picked": enriched.picked},
            response_model=ArchetypeRead,
        )
