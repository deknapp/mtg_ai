"""Canned 'intelligence' for the mock LLM backend.

Each handler takes the structured context an agent passes in and returns schema-valid output,
deterministically and with no API call. This is the fake brain that lets the whole pipeline
run end-to-end in Stage 0 (and in tests) before any real model is wired in. When the real
Anthropic backend is used, none of this runs — the model produces the output instead.
"""

from __future__ import annotations

from collections import Counter

from ..core.models import Card, Color
from .models import (
    Alternative,
    ArchetypeRead,
    CardScore,
    DraftState,
    EvaluationResult,
    PickRecommendation,
)


def _extraction(context: dict) -> DraftState:
    """Stand in for reading the screenshot: return a fixed, realistic Arena draft state."""
    return DraftState(
        picked=["Lightning Strike", "Goblin Guide", "Duress"],
        pack=["Murder", "Shock", "Serra Angel", "Llanowar Elves", "Divination"],
    )


def _archetype(context: dict) -> ArchetypeRead:
    picked: list[Card] = context["picked"]
    counts: Counter[Color] = Counter()
    for card in picked:
        counts.update(card.colors)
    committed = [color for color, _ in counts.most_common() if counts[color] >= 1]
    open_lanes = [c.value for c in Color if c not in committed]
    cmcs = [c.cmc for c in picked if c.type_line and "Creature" in c.type_line]
    curve_gaps = ["Few early creatures"] if not cmcs else []
    label = "/".join(c.value for c in committed) or "colorless"
    return ArchetypeRead(
        committed_colors=committed,
        open_lanes=open_lanes,
        curve_gaps=curve_gaps,
        summary=f"Deck is committing to {label}; keep the aggressive plan and prioritize "
        f"on-color removal and cheap creatures.",
    )


def _evaluation(context: dict) -> EvaluationResult:
    pack: list[Card] = context["pack"]
    scores: list[CardScore] = []
    for card in pack:
        rating = card.rating if card.rating is not None else 5.0
        power = round(min(10.0, rating), 1)
        # Cheap interaction and efficient cards over-perform their raw rating as draft signal.
        signal = round(min(10.0, rating + (0.5 if card.cmc <= 2 else 0.0)), 1)
        scores.append(CardScore(name=card.name, power_score=power, signal_score=signal,
                                note=f"{card.rarity or 'unknown'}; cmc {card.cmc:g}"))
    scores.sort(key=lambda s: s.power_score + s.signal_score, reverse=True)
    return EvaluationResult(ranked=scores)


def _fits(card: Card, committed: list[Color]) -> bool:
    """A card fits if it is colorless or all its colors are already committed."""
    return not card.colors or all(c in committed for c in card.colors)


def _synthesis(context: dict) -> PickRecommendation:
    archetype: ArchetypeRead = context["archetype"]
    evaluation: EvaluationResult = context["evaluation"]
    pack: list[Card] = context["pack"]
    by_name = {c.name: c for c in pack}
    committed = archetype.committed_colors

    def combined(score) -> float:
        return score.power_score + score.signal_score

    # Prefer on-color cards, then raw score. Falls back to best available if nothing fits.
    ranked = sorted(
        evaluation.ranked,
        key=lambda s: (_fits(by_name[s.name], committed), combined(s)),
        reverse=True,
    )
    best = ranked[0]
    best_card = by_name[best.name]
    color_label = "/".join(c.value for c in committed) or "your colors"
    fit_phrase = (
        f"stays in {color_label} and is the strongest on-color option"
        if _fits(best_card, committed)
        else "is the best raw card even though it is off-color"
    )
    rationale = (
        f"Take {best.name}: it {fit_phrase} in the pack (power {best.power_score}, "
        f"signal {best.signal_score}). {archetype.summary}"
    )
    alternatives = [
        Alternative(name=s.name, reason=f"power {s.power_score}, signal {s.signal_score}")
        for s in ranked[1:3]
    ]
    return PickRecommendation(pick=best.name, alternatives=alternatives, rationale=rationale)


HANDLERS = {
    "extraction": _extraction,
    "archetype": _archetype,
    "evaluation": _evaluation,
    "synthesis": _synthesis,
}
