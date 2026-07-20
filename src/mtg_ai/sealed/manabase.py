"""Mana-feasibility optimizer (deterministic).

Given the nonland spells chosen for a deck, split the 17 lands across the deck's colors in
proportion to how many colored pips each color demands, then check each color against a
Frank-Karsten-style "sources needed to cast on curve" threshold (scaled to a 40-card deck).
The point of the check is objective A: don't recommend a deck you can't actually cast.
"""

from __future__ import annotations

from collections import Counter

from ..core.models import Card, Color
from .models import Manabase
from .scoring import BASIC_LAND, pip_counts

TOTAL_LANDS = 17

# Karsten-style sources (40-card deck) to reliably cast a card with N colored pips of one color
# by the turn you want it. Simplified to the pip count; higher-cmc cards get a small discount
# because you have more turns to draw the source.
_SOURCES_FOR_PIPS = {1: 9, 2: 13, 3: 16}


def recommended_sources(pips: int, cmc: float) -> int:
    base = _SOURCES_FOR_PIPS.get(pips, 9 if pips <= 1 else 16)
    discount = max(0, int(cmc) - pips - 1)  # extra time beyond the earliest reasonable turn
    return max(6, base - discount)


def _allocate(pips: Counter[Color], colors: list[Color], total: int) -> dict[Color, int]:
    """Split `total` lands across `colors` in proportion to pip demand (min 1 for a used color)."""
    demand = {c: pips.get(c, 0) for c in colors}
    if sum(demand.values()) == 0:
        # No colored requirements at all -> even split.
        base = total // len(colors)
        alloc = {c: base for c in colors}
        alloc[colors[0]] += total - base * len(colors)
        return alloc

    total_demand = sum(demand.values())
    alloc = {c: (1 if demand[c] > 0 else 0) for c in colors}
    remaining = total - sum(alloc.values())
    # Distribute the rest by largest remainder.
    raw = {c: demand[c] / total_demand * remaining for c in colors}
    floor = {c: int(raw[c]) for c in colors}
    for c in colors:
        alloc[c] += floor[c]
    leftover = remaining - sum(floor.values())
    for c in sorted(colors, key=lambda c: raw[c] - floor[c], reverse=True)[:leftover]:
        alloc[c] += 1
    return alloc


def build_manabase(spells: list[Card], colors: list[Color], total_lands: int = TOTAL_LANDS) -> Manabase:
    pips: Counter[Color] = Counter()
    for card in spells:
        pips.update(pip_counts(card))
    # Only allocate to colors the deck is actually in.
    colors = [c for c in colors] or list(pips.keys()) or [Color.WHITE]

    alloc = _allocate(pips, colors, total_lands)
    lands = {BASIC_LAND[c]: n for c, n in alloc.items() if n > 0}
    sources = {c.value: alloc.get(c, 0) for c in colors}

    notes: list[str] = []
    feasible = True
    for c in colors:
        # Most demanding card of this color: the highest single-card pip count, at its lowest cmc.
        demanding = [(pip_counts(s)[c], s.cmc) for s in spells if pip_counts(s)[c] > 0]
        if not demanding:
            continue
        max_pips = max(p for p, _ in demanding)
        min_cmc = min(cmc for p, cmc in demanding if p == max_pips)
        need = recommended_sources(max_pips, min_cmc)
        have = alloc.get(c, 0)
        if have < need - 1:
            feasible = False
            notes.append(
                f"{c.value}: {have} sources, ~{need} recommended for its "
                f"{'double' if max_pips >= 2 else 'single'}-pip demand — tight."
            )
    if feasible and not notes:
        notes.append("Colored requirements are comfortably supported by this split.")

    return Manabase(
        lands=lands,
        sources=sources,
        total_lands=sum(lands.values()),
        feasible=feasible,
        notes=notes,
    )
