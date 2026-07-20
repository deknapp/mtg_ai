"""Mana-feasibility optimizer (deterministic), splash-aware, Frank-Karsten based.

Objective A: never recommend a deck you can't actually cast. Given the chosen spells and colors:

1. Pull the pool's nonbasic fixing lands (lands whose `produced_mana` covers the deck's colors)
   and count each as a source for every color it makes — this is what lets a splash work.
2. Classify each color as a **main** color or a **splash** (few pips, no early plays).
3. Size each color against a Frank-Karsten 40-card source count: the number of sources needed to
   reliably cast a card with N colored pips by the turn you want it. A late single-pip splash
   needs far fewer sources (~6) than an on-curve double-pip main color (~14) — that math is
   exactly why splashing a bomb off a couple of fixing lands is correct, and why forcing a third
   main color is not. See docs/karsten-manabase.md.

Fixing sources are counted first; basics fill the rest, weighted toward the most-demanding colors.
"""

from __future__ import annotations

from collections import Counter

from ..core.models import Card, Color
from .models import Manabase
from .scoring import BASIC_LAND, pip_counts

TOTAL_LANDS = 17

# Frank-Karsten 40-card "sources needed to cast on curve (~90%)" by colored-pip count.
_SOURCES_ON_CURVE = {1: 9, 2: 14, 3: 17}


def sources_needed(pips: int, cmc: float) -> int:
    """Karsten-style sources for a card needing `pips` of one color, cast around turn `cmc`.

    Each turn you can afford to cast it later than its earliest natural turn (pips+1) shaves ~1
    source — which is what makes a high-cmc single-pip splash cheap to support (down to ~6).
    """
    base = _SOURCES_ON_CURVE.get(pips, 9 if pips <= 1 else 17)
    slack = max(0, int(cmc) - (pips + 1))
    floor = 6 if pips == 1 else 9
    return max(floor, base - slack)


def _color_requirements(spells: list[Card], colors: list[Color]) -> dict[Color, int]:
    """For each color, the max Karsten source requirement across the cards that use it."""
    req: dict[Color, int] = {c: 0 for c in colors}
    for card in spells:
        pc = pip_counts(card)
        for c in colors:
            if pc.get(c):
                req[c] = max(req[c], sources_needed(pc[c], card.cmc))
    return req


def find_fixing(pool_cards: list[Card], colors: list[Color]) -> list[Card]:
    """Nonbasic lands in the pool that produce at least one of the deck's colors."""
    cset = set(colors)
    out = []
    for c in pool_cards:
        if c.is_land and "Basic" not in (c.type_line or "") and set(c.produced_mana) & cset:
            out.append(c)
    return out


def build_manabase(spells: list[Card], colors: list[Color], pool_cards: list[Card] | None = None,
                   total_lands: int = TOTAL_LANDS) -> Manabase:
    pips: Counter[Color] = Counter()
    for card in spells:
        pips.update({c: n for c, n in pip_counts(card).items() if c in colors})
    colors = [c for c in colors if pips.get(c)] or list(colors) or [Color.WHITE]

    # Splash = a color with few total pips and nothing to cast early on it.
    splash = {c for c in colors
              if pips.get(c, 0) <= 4
              and not any(pip_counts(s).get(c) and s.cmc <= 3 for s in spells)}
    # Prefer to keep a splash out of "main"; but if every color is a splash, keep them all.
    if len(splash) == len(colors):
        splash = set()

    req = _color_requirements(spells, colors)

    # Fixing lands from the pool (cap so we still run a healthy basic base).
    fixing = find_fixing(pool_cards or [], colors)
    fixing = sorted(fixing, key=lambda c: len(set(c.produced_mana) & set(colors)), reverse=True)
    fixing = fixing[: min(len(fixing), max(0, total_lands - 8))]
    src_from_fixing: Counter[Color] = Counter()
    for land in fixing:
        for c in set(land.produced_mana) & set(colors):
            src_from_fixing[c] += 1

    remaining = total_lands - len(fixing)
    # Basics each color still needs to hit its requirement, then distribute the rest by pip weight.
    need = {c: max(0, req[c] - src_from_fixing[c]) for c in colors}
    basics = dict(need)
    used = sum(basics.values())
    if used > remaining:
        # Greedy build the mana can't fully support — scale proportionally and flag below.
        scale = remaining / used if used else 0
        basics = {c: int(basics[c] * scale) for c in colors}
        used = sum(basics.values())
    # Distribute leftover basics by pip demand (main colors first).
    leftover = remaining - used
    order = sorted(colors, key=lambda c: (c not in splash, pips.get(c, 0)), reverse=True)
    i = 0
    while leftover > 0 and order:
        basics[order[i % len(order)]] += 1
        leftover -= 1
        i += 1

    lands: dict[str, int] = {}
    for land in fixing:
        lands[land.name] = lands.get(land.name, 0) + 1
    for c in colors:
        if basics.get(c):
            lands[BASIC_LAND[c]] = lands.get(BASIC_LAND[c], 0) + basics[c]

    sources = {c.value: src_from_fixing[c] + basics.get(c, 0) for c in colors}

    notes: list[str] = []
    feasible = True
    for c in colors:
        have = sources[c.value]
        if have < req[c] - 1:
            feasible = False
            kind = "splash" if c in splash else "main"
            notes.append(f"{c.value} ({kind}): {have} sources, ~{req[c]} recommended — tight.")
    if fixing:
        notes.append(f"Fixing: {', '.join(sorted({l.name for l in fixing}))} "
                     f"support the {'/'.join(sorted(x.value for x in splash)) or 'core'} colors.")
    if feasible and not any('tight' in n for n in notes):
        notes.insert(0, "Colored requirements are comfortably supported.")

    return Manabase(
        lands=lands,
        sources=sources,
        fixing=sorted({l.name for l in fixing}),
        splash_colors=sorted(splash, key=lambda c: c.value),
        total_lands=sum(lands.values()),
        feasible=feasible,
        notes=notes,
    )
