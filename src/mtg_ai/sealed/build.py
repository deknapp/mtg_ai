"""Deterministic sealed build engine: color choice + card selection + curve.

This is the substance of the builder and uses no LLM — it's objective optimization over the
pool (objectives A/B: mana feasibility via `manabase`, and bombs prioritized in selection). An
optional LLM synergy/rationale pass sits on top in the pipeline; the deck it produces is already
legal and castable on its own.
"""

from __future__ import annotations

from itertools import combinations
from statistics import mean

from ..core.models import Card, Color
from .manabase import build_manabase
from .models import ColorPairScore, DeckCard, Pool, SealedDeck
from .scoring import castable_in, effective_rating, is_bomb, role

DECK_SPELLS = 23  # 40-card deck = 23 nonland + 17 lands
MIN_CREATURES = 13  # a limited deck needs bodies; nudge selection toward this floor

ALL_PAIRS = list(combinations(list(Color), 2))


def _sort_key(card: Card):
    # Bombs float to the top, then raw win-rate.
    return (is_bomb(card), effective_rating(card))


def score_color_pairs(pool: Pool) -> list[ColorPairScore]:
    """Score all ten two-color pairs by the strength of the best 23 castable spells."""
    scores: list[ColorPairScore] = []
    for pair in ALL_PAIRS:
        cset = set(pair)
        playables = [c for c in pool.spells if castable_in(c, cset)]
        ranked = sorted(playables, key=_sort_key, reverse=True)
        top = ranked[:DECK_SPELLS]
        deck_score = sum(effective_rating(c) for c in top)
        scores.append(
            ColorPairScore(
                label="".join(c.value for c in pair),
                colors=list(pair),
                playable_count=len(playables),
                deck_score=round(deck_score, 3),
                avg_rating=round(mean(effective_rating(c) for c in top), 3) if top else 0.0,
                bomb_count=sum(1 for c in playables if is_bomb(c)),
                removal_count=sum(1 for c in top if role(c) == "removal"),
                creature_count=sum(1 for c in top if c.is_creature),
                note=(
                    f"{len(playables)} castable spells; "
                    f"{sum(1 for c in playables if is_bomb(c))} bomb(s)"
                    + ("" if len(playables) >= DECK_SPELLS else "  ⚠ thin on playables")
                ),
            )
        )
    # Best deck first: total power of the top 23, then bomb count as a tie-break.
    scores.sort(key=lambda s: (s.deck_score, s.bomb_count), reverse=True)
    return scores


def best_colors(scores: list[ColorPairScore]) -> list[Color]:
    return scores[0].colors if scores else [Color.WHITE, Color.BLUE]


def select_spells(pool: Pool, colors: list[Color], n: int = DECK_SPELLS) -> list[Card]:
    """Pick the best `n` castable spells, prioritising bombs and keeping a creature floor."""
    cset = set(colors)
    candidates = sorted(
        (c for c in pool.spells if castable_in(c, cset)), key=_sort_key, reverse=True
    )
    chosen = candidates[:n]

    # Curve/bodies guard: if we're short on creatures, swap the weakest non-creatures for the
    # best available creatures outside the current 23.
    def creatures_in(cards: list[Card]) -> int:
        return sum(1 for c in cards if c.is_creature)

    pool_creatures = [c for c in candidates if c.is_creature and c not in chosen]
    while creatures_in(chosen) < MIN_CREATURES and pool_creatures:
        noncreatures = [c for c in chosen if not c.is_creature and not is_bomb(c)]
        if not noncreatures:
            break
        weakest = min(noncreatures, key=effective_rating)
        best_creature = pool_creatures.pop(0)
        chosen[chosen.index(weakest)] = best_creature

    return sorted(chosen, key=lambda c: (c.cmc, -effective_rating(c)))


def _curve(spells: list[Card]) -> dict[str, int]:
    curve = {k: 0 for k in ["1", "2", "3", "4", "5", "6+"]}
    for c in spells:
        key = "6+" if c.cmc >= 6 else str(int(c.cmc)) if c.cmc >= 1 else "1"
        curve[key] += 1
    return curve


def _deck_card(card: Card) -> DeckCard:
    return DeckCard(
        name=card.name,
        cmc=card.cmc,
        colors=card.colors,
        rarity=card.rarity,
        rating=card.rating,
        rating_source=card.rating_source,
        is_bomb=is_bomb(card),
        role=role(card),
    )


def _assemble(pool: Pool, colors: list[Color], spells: list[Card], rationale: str) -> SealedDeck:
    """Turn a chosen set of spells into a full 40-card deck (manabase, curve, composition)."""
    manabase = build_manabase(spells, colors, pool.cards)  # pool.cards → fixing lands for splashes
    deck_cards = [_deck_card(c) for c in spells]

    cset = set(colors)
    sideboard = [
        _deck_card(c)
        for c in sorted(
            (c for c in pool.spells if castable_in(c, cset) and c not in spells),
            key=_sort_key,
            reverse=True,
        )[:6]
    ]

    return SealedDeck(
        colors=colors,
        spells=deck_cards,
        manabase=manabase,
        curve=_curve(spells),
        bombs=[dc.name for dc in deck_cards if dc.is_bomb],
        creatures=sum(1 for dc in deck_cards if dc.role == "creature"),
        removal=sum(1 for dc in deck_cards if dc.role == "removal"),
        total_cards=len(deck_cards) + manabase.total_lands,
        sideboard_highlights=sideboard,
        rationale=rationale,
    )


def build_deck(pool: Pool, colors: list[Color], rationale: str = "") -> SealedDeck:
    """Deterministic build: pick the best 23 spells for `colors`, then assemble."""
    return _assemble(pool, colors, select_spells(pool, colors), rationale)


def resolve_names(pool: Pool, names: list[str]) -> list[Card]:
    """Map the AI's chosen card names back to pool cards, honoring duplicate copies.

    Exact (case-insensitive) match first, then a fuzzy fallback for minor misspellings. Each
    physical copy in the pool is consumed at most once, so a name listed twice pulls two copies.
    """
    from difflib import get_close_matches

    remaining = list(pool.spells)
    by_lower: dict[str, list[int]] = {}
    for i, c in enumerate(remaining):
        by_lower.setdefault(c.name.lower(), []).append(i)
    used: set[int] = set()

    def take(idxs: list[int]) -> Card | None:
        for i in idxs:
            if i not in used:
                used.add(i)
                return remaining[i]
        return None

    chosen: list[Card] = []
    for name in names:
        key = name.strip().lower()
        card = take(by_lower.get(key, []))
        if card is None:  # fuzzy fallback against unused names
            avail = {c.name.lower() for i, c in enumerate(remaining) if i not in used}
            m = get_close_matches(key, list(avail), n=1, cutoff=0.8)
            if m:
                card = take(by_lower.get(m[0], []))
        if card is not None:
            chosen.append(card)
    return chosen


def assemble_deck(pool: Pool, colors: list[Color], names: list[str], rationale: str) -> SealedDeck:
    """AI path: resolve the AI's chosen names, top up / trim to 23 spells, then assemble.

    Keeps mana feasibility rigorous — the deterministic manabase optimizer runs on whatever
    colors and spells the AI committed to.
    """
    spells = resolve_names(pool, names)
    cset = set(colors)
    if len(spells) < DECK_SPELLS:
        # Top up with the best remaining castable spells the AI didn't name.
        extra = sorted(
            (c for c in pool.spells if castable_in(c, cset) and c not in spells),
            key=_sort_key,
            reverse=True,
        )
        spells += extra[: DECK_SPELLS - len(spells)]
    if len(spells) > DECK_SPELLS:
        spells = sorted(spells, key=_sort_key, reverse=True)[:DECK_SPELLS]
    spells = sorted(spells, key=lambda c: (c.cmc, -effective_rating(c)))
    return _assemble(pool, colors, spells, rationale)
