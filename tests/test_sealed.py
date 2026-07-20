"""Sealed builder tests — all offline (no Arena log, no network)."""

from __future__ import annotations

from mtg_ai.core.data import CardRepository
from mtg_ai.core.models import Card, Color
from mtg_ai.sealed.build import build_deck, score_color_pairs, select_spells
from mtg_ai.sealed.enrichment import SealedEnrichment
from mtg_ai.sealed.ingest_log import parse_pool
from mtg_ai.sealed.manabase import build_manabase, recommended_sources
from mtg_ai.sealed.models import Pool
from mtg_ai.sealed.pipeline import SealedPipeline
from mtg_ai.sealed.ingest_log import ParsedPool
from mtg_ai.core.config import Settings
from mtg_ai.sealed.scoring import is_bomb, is_removal, pip_counts


# --- helpers ------------------------------------------------------------------------------


def _card(name, cost, colors, cmc, *, type_line="Creature — Hero", rarity="common",
          rating=None, oracle="", arena_id=None) -> Card:
    return Card(name=name, mana_cost=cost, cmc=cmc, colors=colors, type_line=type_line,
                rarity=rarity, rating=rating, oracle_text=oracle, arena_id=arena_id)


def _mono_pool(color: Color, letter: str, n=30) -> Pool:
    """A pool deep in one color plus a few off-color cards, for deterministic color choice."""
    cards = [
        _card(f"{letter}Guy{i}", f"{{1}}{{{letter}}}", [color], 2, rating=0.55 + i * 0.001,
              arena_id=1000 + i)
        for i in range(n)
    ]
    # a couple of splashable colorless
    cards.append(_card("Colorless Golem", "{4}", [], 4, type_line="Artifact Creature — Golem",
                       arena_id=2000))
    return Pool(set_code="tst", cards=cards)


# --- ingest_log ---------------------------------------------------------------------------


def test_parse_pool_picks_largest_cardpool_and_event():
    log = (
        'DETAILED LOGS: ENABLED\n'
        '{"CardPool":[1,2,3]}\n'
        '{"InternalEventName":"ArenaDirect_MSH_Play_Sealed_20260717"}\n'
        '{"CardPool":[10,11,12,13,14]}\n'  # a later, larger pool
    )
    parsed = parse_pool(log)
    assert parsed.grp_ids == [10, 11, 12, 13, 14]
    assert parsed.set_code == "msh"
    assert parsed.detailed_logs is True


def test_parse_pool_reports_detailed_off_when_no_pool():
    parsed = parse_pool("DETAILED LOGS: DISABLED\n(no card data here)\n")
    assert parsed.grp_ids == []
    assert parsed.detailed_logs is False


# --- scoring ------------------------------------------------------------------------------


def test_pip_counts_and_removal_and_bomb():
    murder = _card("Murder", "{1}{B}{B}", [Color.BLACK], 3, type_line="Instant",
                   rarity="uncommon", oracle="Destroy target creature.")
    assert pip_counts(murder)[Color.BLACK] == 2
    assert is_removal(murder) is True
    # a rare above the bomb win-rate threshold is a bomb; a rated common is not
    bomb = _card("Big Rare", "{3}{R}", [Color.RED], 4, rarity="rare", rating=0.58)
    assert is_bomb(bomb) is True
    assert is_bomb(_card("Filler", "{R}", [Color.RED], 1, rating=0.52)) is False


# --- manabase -----------------------------------------------------------------------------


def test_recommended_sources_double_pip_needs_more():
    assert recommended_sources(2, 3.0) > recommended_sources(1, 3.0)


def test_manabase_splits_by_pip_demand_and_flags_tight_double_pip():
    # A deck heavy on double-blue but light white -> more Islands, and a feasibility warning.
    spells = [_card(f"UU{i}", "{U}{U}", [Color.BLUE], 2) for i in range(6)]
    spells += [_card(f"W{i}", "{2}{W}", [Color.WHITE], 3) for i in range(4)]
    mb = build_manabase(spells, [Color.WHITE, Color.BLUE], total_lands=17)
    assert mb.total_lands == 17
    assert mb.sources["U"] > mb.sources["W"]  # follows the pip demand
    # Loading up on Islands for double-blue starves White -> an honest feasibility warning.
    assert mb.feasible is False
    assert any("recommended" in n for n in mb.notes)


def test_manabase_even_split_when_no_pips():
    mb = build_manabase([_card("Colorless", "{2}", [], 2, type_line="Artifact")],
                        [Color.WHITE, Color.BLUE])
    assert mb.total_lands == 17


# --- build --------------------------------------------------------------------------------


def test_color_pairs_prefers_the_deep_color():
    pool = _mono_pool(Color.RED, "R")
    scores = score_color_pairs(pool)
    assert Color.RED in scores[0].colors  # the deepest color anchors the best pair


def test_build_deck_is_a_legal_40():
    pool = _mono_pool(Color.GREEN, "G")
    deck = build_deck(pool, [Color.GREEN, Color.WHITE])
    assert len(deck.spells) == 23
    assert deck.manabase.total_lands == 17
    assert deck.total_cards == 40


def test_selection_prioritises_bombs():
    pool = _mono_pool(Color.BLUE, "U")
    bomb = _card("Sphinx Bomb", "{4}{U}", [Color.BLUE], 5, rarity="mythic", rating=0.60,
                 arena_id=9999)
    pool.cards.append(bomb)
    chosen = select_spells(pool, [Color.BLUE, Color.WHITE])
    assert any(c.name == "Sphinx Bomb" for c in chosen)


# --- pipeline (with an in-memory arena-id repo) -------------------------------------------


class _InMemoryRepo(CardRepository):
    def __init__(self, cards: list[Card]) -> None:
        self._by_id = {c.arena_id: c for c in cards}
        self._by_name = {c.name.lower(): c for c in cards}

    def lookup(self, name):
        return self._by_name.get(name.lower())

    def all_names(self):
        return list(self._by_name)

    def lookup_by_arena_id(self, arena_id):
        return self._by_id.get(arena_id)


def test_pipeline_end_to_end_offline():
    pool = _mono_pool(Color.BLACK, "B")
    repo = _InMemoryRepo(pool.cards)
    parsed = ParsedPool(grp_ids=[c.arena_id for c in pool.cards], set_code="tst")

    result = SealedPipeline(repo, Settings(default_set="tst"), ratings=None).run(parsed)

    assert result.deck.total_cards == 40
    assert len(result.deck.spells) == 23
    assert Color.BLACK in result.chosen_colors
    assert len(result.colorpair_scores) == 10  # all pairs scored
    assert {c.agent for c in result.cost_log} == {"enrichment", "colorpairs", "deckbuilder"}


def test_enrichment_flags_unresolved_ids():
    pool = _mono_pool(Color.RED, "R", n=3)
    repo = _InMemoryRepo(pool.cards)
    parsed = ParsedPool(grp_ids=[c.arena_id for c in pool.cards] + [999999], set_code="tst")
    enriched = SealedEnrichment(repo).run(parsed, "tst")
    assert 999999 in enriched.unresolved_ids
    assert len(enriched.cards) == len(pool.cards)
