"""AI deckbuilder agent — the reasoning centerpiece of the sealed builder.

Strong tier (Opus) with adaptive thinking. It receives the whole pool with 17Lands win-rates,
mana costs, types, rarity, and oracle text, and reasons out the best build: colors (2 or 3),
the maindeck spells, the synergies to lean on, and the bombs to build around. 17Lands is a
*guide* to card power, not the sole input — the model weighs synergy, curve, removal, and mana.
The deterministic manabase optimizer then enforces castability on whatever it chose.
"""

from __future__ import annotations

from ..core.llm import LLM
from ..core.models import CostEntry
from .models import LLMBuild, Pool
from .ratings import RatingsResult
from .scoring import effective_rating, is_removal

SYSTEM = (
    "You are an expert Magic: The Gathering sealed deck builder. You are given a player's full "
    "sealed pool for a single set. Build the best 40-card deck: 23 nonland cards + 17 lands.\n\n"
    "How to reason:\n"
    "- Card power: use the 17Lands games-in-hand win rate (GIHWR) as a strong GUIDE to raw power "
    "(higher is better; ~57%+ is excellent, ~50% is replaceable), but it is context-independent — "
    "weigh it against synergy, curve, removal density, evasion, and bombs.\n"
    "- Colors: prefer the best two colors. Only go three colors when the pool's fixing (dual "
    "lands, mana rocks, artifact ramp) and a real payoff justify it — say so explicitly if you do.\n"
    "- Bombs: build around high-impact rares/mythics (game-ending threats, premium removal).\n"
    "- Synergy: exploit the set's mechanics and card types — artifact/equipment payoffs, tribal "
    "themes, tokens, counters, sacrifice, graveyard — wherever the pool supports them.\n"
    "- Mana & curve: keep a castable curve; don't overload on 5+ drops; ensure ~15-17 creatures "
    "unless the deck is deliberately control.\n\n"
    "Pick maindeck cards ONLY from the pool, by their exact printed names (duplicates allowed)."
)


class SealedDeckBuilderAgent:
    name = "deckbuilder"

    def __init__(self, llm: LLM, model: str) -> None:
        self._llm = llm
        self._model = model

    def _describe(self, pool: Pool, ratings: RatingsResult | None) -> str:
        src = ratings.source_format if ratings and ratings.usable else None
        lines = []
        for c in sorted(pool.spells, key=effective_rating, reverse=True):
            gih = f"{c.rating*100:.1f}%" if c.rating is not None else "n/a"
            text = (c.oracle_text or "").replace("\n", " ")
            if len(text) > 140:
                text = text[:140] + "…"
            tag = " [removal]" if is_removal(c) else ""
            lines.append(
                f"- {c.name} | {c.mana_cost or '—'} | {c.type_line or '?'} | {c.rarity or '?'} "
                f"| GIHWR {gih}{tag} | {text}"
            )
        header = (
            f"Pool for set {pool.set_code} ({len(pool.spells)} nonland cards). "
            + (f"GIHWR is 17Lands {src} data." if src else "No 17Lands win-rates for this set; "
               "judge power from cards + rarity.")
        )
        return header + "\n\n" + "\n".join(lines)

    def run(self, pool: Pool, ratings: RatingsResult | None) -> tuple[LLMBuild, CostEntry]:
        user = (
            self._describe(pool, ratings)
            + "\n\nBuild the best 40-card sealed deck. Return the colors, the 23 maindeck "
            "nonland card names, the bombs, the key synergies, and a 3-4 sentence rationale."
        )
        return self._llm.structured(
            agent=self.name,
            model=self._model,
            system=SYSTEM,
            user=user,
            context={"pool": pool, "ratings": ratings},
            response_model=LLMBuild,
            max_tokens=8000,   # room for adaptive thinking + the structured answer
            thinking=True,
        )
