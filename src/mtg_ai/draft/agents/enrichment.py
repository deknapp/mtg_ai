"""Card enrichment: deterministic, no LLM.

Joins each extracted card name against the data layer to attach real facts (types, colors,
mana, rules text, rating). Names that don't resolve exactly are fuzzy-matched against the
known set (the vision agent makes OCR-style misreads like "Cobot Domination" for "Robot
Domination"); names that still don't resolve are kept and flagged, not dropped.
"""

from __future__ import annotations

from difflib import get_close_matches
from functools import cached_property

from ...core.data import CardRepository
from ...core.models import Card
from ..models import DraftState, EnrichedDraftState

# SequenceMatcher ratio needed to accept a fuzzy correction. High enough to fix single-word
# OCR slips ("Deathblok"->"Deathlok") without mapping a genuinely-unknown card onto a real one.
_FUZZY_CUTOFF = 0.72


class EnrichmentAgent:
    name = "enrichment"

    def __init__(self, repository: CardRepository) -> None:
        self._repo = repository

    @cached_property
    def _names_by_lower(self) -> dict[str, str]:
        return {n.lower(): n for n in self._repo.all_names()}

    def _resolve(self, name: str) -> Card:
        card = self._repo.lookup(name)
        if card is not None:
            return card
        # Fuzzy fallback: correct an OCR misread to the closest real card name in the set.
        match = get_close_matches(
            name.lower(), list(self._names_by_lower), n=1, cutoff=_FUZZY_CUTOFF
        )
        if match:
            corrected = self._repo.lookup(self._names_by_lower[match[0]])
            if corrected is not None:
                return corrected
        return Card(name=name, unresolved=True)

    def run(self, state: DraftState) -> EnrichedDraftState:
        return EnrichedDraftState(
            picked=[self._resolve(n) for n in state.picked],
            pack=[self._resolve(n) for n in state.pack],
        )
