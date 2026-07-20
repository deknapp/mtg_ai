"""Mock intelligence for the sealed AI deckbuilder.

Lets the AI path run end-to-end with zero API cost (tests, offline demo): the mock "AI" just
reuses the deterministic engine's color choice + selection and reports it as an LLMBuild. When
the real Anthropic backend is used, none of this runs — the model reasons instead.
"""

from __future__ import annotations

from .build import best_colors, score_color_pairs, select_spells
from .models import LLMBuild, Pool
from .scoring import is_bomb


def _deckbuilder(context: dict) -> LLMBuild:
    pool: Pool = context["pool"]
    scores = score_color_pairs(pool)
    colors = best_colors(scores)
    spells = select_spells(pool, colors)
    return LLMBuild(
        colors=colors,
        maindeck=[c.name for c in spells],
        bombs=[c.name for c in spells if is_bomb(c)],
        synergies=["(mock) deterministic selection — enable real models for AI synergy reasoning"],
        rationale="Mock build: strongest two-color core by 17Lands win-rate. "
        "Flip on real models for genuine synergy/3-color reasoning.",
    )


HANDLERS = {"deckbuilder": _deckbuilder}
