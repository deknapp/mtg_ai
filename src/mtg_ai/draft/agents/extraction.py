"""Vision/Extraction agent: screenshot -> structured draft state (card names only).

Cheap-tier, multimodal. Segments the single screenshot into the already-picked pool and the
current pack. Card *facts* come later from the data layer, not from this agent.
"""

from __future__ import annotations

import base64

from ...core.llm import LLM
from ...core.models import CostEntry
from ..models import DraftState

SYSTEM = (
    "You are the extraction agent in an MTG Arena draft assistant. You are given one "
    "screenshot of an in-progress draft. Read the Arena layout carefully:\n"
    "- CURRENT PACK: the large grid of full card images in the center/left of the screen. "
    "These are the cards on offer this pick; you choose exactly one. The header above them "
    "reads 'Pack X | Pick Y'. There are usually many of them (up to 14 or 15 on pick 1).\n"
    "- PICKED POOL: the vertical list on the RIGHT-HAND rail under the 'Deck' heading (e.g. "
    "'Deck 4/40 Cards'), shown as compact text rows with a quantity like '1x'. Also include "
    "any rows under a 'Sideboard' heading on that same right rail. IMPORTANT: on Pack 1 Pick 1 "
    "the Deck shows '0/40 Cards' and this list is EMPTY — in that case 'picked' is an empty "
    "list and every card in the center grid belongs to 'pack'.\n"
    "Never put the center-grid cards into 'picked'. Never leave 'pack' empty when the center "
    "grid has cards. Return ONLY card names, exactly as printed. Do not add facts or commentary."
)


class ExtractionAgent:
    name = "extraction"

    def __init__(self, llm: LLM, model: str) -> None:
        self._llm = llm
        self._model = model

    def run(self, image_bytes: bytes | None, media_type: str = "image/png") -> tuple[DraftState, CostEntry]:
        context: dict = {}
        if image_bytes:
            context["image_b64"] = base64.standard_b64encode(image_bytes).decode()
            context["image_media_type"] = media_type
        return self._llm.structured(
            agent=self.name,
            model=self._model,
            system=SYSTEM,
            user=(
                "Extract the picked pool (right-rail Deck + Sideboard list) and the current "
                "pack (center card grid) from this draft screenshot. If the Deck shows 0 cards, "
                "return picked as an empty list and put all center-grid cards in pack."
            ),
            context=context,
            response_model=DraftState,
        )
