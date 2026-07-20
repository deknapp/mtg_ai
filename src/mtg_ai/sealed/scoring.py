"""Shared card heuristics for the sealed builder (deterministic).

Everything here operates on the 17Lands GIH win-rate scale (~0.40–0.62). Cards with no rating
(e.g. Sealed data not published yet, or a card 17Lands never saw) get a rarity-based baseline so
an unrated bomb still competes with a rated common.
"""

from __future__ import annotations

import re
from collections import Counter

from ..core.models import Card, Color

BASIC_LAND = {
    Color.WHITE: "Plains",
    Color.BLUE: "Island",
    Color.BLACK: "Swamp",
    Color.RED: "Mountain",
    Color.GREEN: "Forest",
}

# Baseline effective rating when 17Lands has no win-rate for the card, by rarity.
_BASELINE = {"common": 0.500, "uncommon": 0.520, "rare": 0.550, "mythic": 0.565}
# A rare/mythic at or above this win-rate is treated as a bomb (worth building toward).
BOMB_WR = 0.560

_PIP_RE = re.compile(r"\{([WUBRG])\}")
_REMOVAL_RE = re.compile(
    r"(destroy target|exile target (?:creature|permanent|artifact|enchantment)"
    r"|deals? \d+ damage to (?:any target|target creature|target attacking|it)"
    r"|fights? target|-\d+/-\d+|gets -\d+/-\d+)",
    re.IGNORECASE,
)


def effective_rating(card: Card) -> float:
    """Card power on the GIH win-rate scale, falling back to a rarity baseline."""
    if card.rating is not None:
        return card.rating
    return _BASELINE.get((card.rarity or "common").lower(), 0.500)


def pip_counts(card: Card) -> Counter[Color]:
    """Colored mana symbols in the card's cost, e.g. {1}{B}{B} -> {BLACK: 2}."""
    counts: Counter[Color] = Counter()
    for sym in _PIP_RE.findall(card.mana_cost or ""):
        counts[Color(sym)] += 1
    return counts


def is_removal(card: Card) -> bool:
    return bool(card.oracle_text and _REMOVAL_RE.search(card.oracle_text))


def role(card: Card) -> str:
    if card.is_creature:
        return "creature"
    if is_removal(card):
        return "removal"
    return "other"


def is_bomb(card: Card) -> bool:
    return (card.rarity or "").lower() in {"rare", "mythic"} and effective_rating(card) >= BOMB_WR


def castable_in(card: Card, colors: set[Color]) -> bool:
    """A nonland card is castable in a color pair if all its colored pips are within it."""
    return all(c in colors for c in card.colors)
