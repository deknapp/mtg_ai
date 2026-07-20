"""AI deckbuilder agent — the reasoning centerpiece, grounded in the quantitative scaffold.

Strong tier (Opus) with adaptive thinking. It receives:
  - every card with its best-available 17Lands win rate, TAGGED with the source format
    (event-sealed vs generic-sealed vs draft-proxy) and game-count confidence,
  - the pool's fixing lands and exactly what colors they produce (so a splash is on the table),
  - the deterministic color-pair scores (the quantitative color read), and
  - explicit BOMB flags for rares/mythics that have no win rate yet, so a missing number never
    buries a bomb.
It reasons over that scaffold — colors (2 or 3), the maindeck, synergies, bombs — and the
deterministic Karsten manabase then enforces castability on whatever it chose.
"""

from __future__ import annotations

from ..core.llm import LLM
from ..core.models import CostEntry
from .models import ColorPairScore, LLMBuild, Pool, PriorBuild, SplashSuggestion
from .scoring import effective_rating, is_removal

SYSTEM = (
    "You are an expert Magic: The Gathering SEALED deck builder. You get a player's full sealed "
    "pool for one set and build the best 40-card deck: 23 nonland cards + 17 lands.\n\n"
    "Reading the data:\n"
    "- Each card shows a 17Lands games-in-hand win rate (GIHWR) TAGGED with its source: "
    "[event] = the player's exact Arena Direct Sealed event (best), [sealed] = generic sealed, "
    "[draft] = draft data used as a power proxy. SEALED win rates run a few points higher than "
    "draft, so do NOT rank a [draft] number directly against a [sealed] one — weigh the source. "
    "Also weigh the game count: a number from tens of games is noisy; thousands is solid.\n"
    "- Cards flagged BOMB (rare/mythic, no win rate yet) have NO 17Lands data — new sets take "
    "weeks to publish rare win rates. Judge these on the card text: game-ending threats, premium "
    "removal, and card-advantage engines are what win sealed. Do not discount them for lacking a "
    "number.\n\n"
    "How to build (this is SEALED, a slow, bomb-driven format):\n"
    "- Bombs and removal win games; play your best ones. Card quality > curve.\n"
    "- Prefer two colors, but a THREE-color build is correct when the pool's fixing lands (listed) "
    "support a light splash of a few high-impact cards — a late single-pip splash needs only a "
    "couple of sources. Use the fixing; splash your best bombs when it's supported.\n"
    "- Exploit synergy the pool offers (artifacts/equipment, tribal, tokens, counters, the set's "
    "mechanics) — this is where you beat the raw win rates.\n"
    "- Keep a castable curve and ~15-17 creatures unless deliberately controlling.\n\n"
    "Pick maindeck cards ONLY from the pool by their exact printed names (duplicates allowed)."
)

_SRC = {"ArenaDirect_Sealed": "event", "Sealed": "sealed", "TradSealed": "sealed",
        "PremierDraft": "draft", "TradDraft": "draft", "QuickDraft": "draft"}


class SealedDeckBuilderAgent:
    name = "deckbuilder"

    def __init__(self, llm: LLM, model: str) -> None:
        self._llm = llm
        self._model = model

    def _card_line(self, c) -> str:
        if c.rating is not None:
            src = _SRC.get(c.rating_source or "", c.rating_source or "?")
            sig = f"GIHWR {c.rating*100:.1f}% [{src},{c.rating_games or 0}g]"
        elif (c.rarity or "").lower() in {"rare", "mythic"}:
            sig = "BOMB? (no 17Lands data — judge from card)"
        else:
            sig = "GIHWR n/a"
        tag = " [removal]" if is_removal(c) else ""
        text = (c.oracle_text or "").replace("\n", " ")
        if len(text) > 140:
            text = text[:140] + "…"
        return f"- {c.name} | {c.mana_cost or '—'} | {c.type_line or '?'} | {c.rarity or '?'} " \
               f"| {sig}{tag} | {text}"

    def _describe(self, pool: Pool, scores: list[ColorPairScore]) -> str:
        parts = [f"POOL for set {pool.set_code} — {len(pool.spells)} nonland cards."]

        # Quantitative color read (deterministic color-pair scores).
        parts.append("\nCOLOR-PAIR SCORES (sum of the best 23 castable cards' ratings; higher=better):")
        for s in scores[:6]:
            parts.append(f"  {s.label}: score {s.deck_score:.2f} | {s.playable_count} playable, "
                         f"{s.bomb_count} bomb, {s.removal_count} removal, {s.creature_count} creatures")

        # Fixing lands available (enables splashes) — every nonbasic land that taps for color.
        fixing = [c for c in pool.cards if c.is_land and "Basic" not in (c.type_line or "")
                  and c.produced_mana]
        if fixing:
            parts.append("\nFIXING LANDS IN POOL (enable splashes — what each taps for):")
            for c in fixing:
                cols = "".join(x.value for x in c.produced_mana)
                r = f" GIHWR {c.rating*100:.0f}%" if c.rating is not None else ""
                parts.append(f"  {c.name} → {cols}{r}")

        parts.append("\nCARDS (win rates tagged by source; BOMB = rare/mythic with no data yet):")
        for c in sorted(pool.spells, key=effective_rating, reverse=True):
            parts.append(self._card_line(c))
        return "\n".join(parts)

    def _splash_section(self, splashes: list[SplashSuggestion]) -> str:
        if not splashes:
            return ""
        lines = [
            "\nTHREE-COLOR / SPLASH OPPORTUNITIES — a 2-color base + a LIGHT splash of a third "
            "color for bombs/removal. Splashing is often the strongest sealed build, but only when "
            "the pool has fixing for it. The deterministic manabase will enforce castability and "
            "flag a splash it can't support, so lean in when the fixing is here:"
        ]
        for s in splashes:
            bombs = f"{s.added_bomb_count} bomb" if s.added_bomb_count else "no bomb"
            lines.append(
                f"  {s.label}: adds {', '.join(s.added_cards)} ({bombs}) | "
                f"+{s.power_gain:.3f} power over {''.join(c.value for c in s.base_colors)} | "
                f"{s.fixing_count} fixing land(s) make {s.splash_color.value}"
                + (f" ({', '.join(s.fixing_lands)})" if s.fixing_lands else "")
            )
        lines.append(
            "When a splash adds a bomb or clear power AND has ~3+ fixing sources, PREFER the "
            "three-color build: put all three colors in `colors` and include the splash cards in "
            "the maindeck. Do not force a third *main* color without fixing."
        )
        return "\n".join(lines)

    def _prior_section(self, prior: PriorBuild | None) -> str:
        if not prior or not prior.maindeck:
            return ""
        return (
            "\nYOUR PREVIOUS BUILD — revise THIS deck to satisfy the new guidance. Keep what still "
            "works and change what the guidance asks (you may switch colors, add/drop a splash, or "
            "swap cards). Call out what you changed and why in the rationale.\n"
            f"  Colors: {''.join(c.value for c in prior.colors)}\n"
            f"  Maindeck ({len(prior.maindeck)}): {', '.join(prior.maindeck)}\n"
            f"  Rationale: {prior.rationale}"
        )

    def run(
        self,
        pool: Pool,
        scores: list[ColorPairScore],
        guidance: str = "",
        splashes: list[SplashSuggestion] | None = None,
        prior: PriorBuild | None = None,
    ) -> tuple[LLMBuild, CostEntry]:
        user = (
            self._describe(pool, scores)
            + self._splash_section(splashes or [])
            + "\n\nBuild the best 40-card sealed deck. Consider two-color AND two-color-plus-splash "
            "(three-color) builds; pick whichever is strongest for THIS pool. Return the colors "
            "(2 or 3), the 23 maindeck nonland card names, the bombs, the key synergies, and a 3-4 "
            "sentence rationale that says why these colors and whether you're splashing (and off "
            "what fixing)."
        )
        user += self._prior_section(prior)
        guidance = (guidance or "").strip()
        if guidance:
            # The player's steer takes priority over the data-driven default — but only within
            # what's actually buildable: the deterministic manabase still enforces castability, so
            # honor the intent (colors, archetype, must-include cards) and say how you applied it.
            user += (
                "\n\nPLAYER GUIDANCE (honor this over the default read where the pool allows it; "
                "if it's not feasible, do the closest legal thing and explain the tradeoff in the "
                f"rationale):\n{guidance}"
            )
        return self._llm.structured(
            agent=self.name,
            model=self._model,
            system=SYSTEM,
            user=user,
            context={"pool": pool, "scores": scores},
            response_model=LLMBuild,
            max_tokens=8000,
            thinking=True,
        )
