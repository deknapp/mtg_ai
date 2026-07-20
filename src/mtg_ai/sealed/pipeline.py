"""Sealed pipeline orchestration.

    Arena log (ParsedPool) -> enrichment -> color-pair scoring -> deck build

Color choice, selection, and the manabase are deterministic (cheap, inspectable, free). The
17Lands ratings that ground them are fetched+cached per-card (best available format). When the
AI build is requested, an Opus deckbuilder reasons over that scaffold and the deterministic
manabase enforces castability on whatever it chose; otherwise a deterministic build is returned.
"""

from __future__ import annotations

from pathlib import Path

from ..core.config import Settings, get_secrets, get_settings
from ..core.data import CardRepository, SqliteCardRepository, StubCardRepository
from ..core.llm import LLM, build_llm
from ..core.models import Color, CostEntry
from .build import assemble_deck, best_colors, build_deck, score_color_pairs
from .deckbuilder_llm import SealedDeckBuilderAgent
from .enrichment import SealedEnrichment
from .ingest_log import ParsedPool
from .mock_backend import HANDLERS
from .models import ColorPairScore, Pool, SealedResult
from .ratings import SEALED_LADDER, RatingsCache, RatingsIndex


def _rationale(pool: Pool, scores: list[ColorPairScore], colors: list[Color],
               ratings: RatingsIndex | None) -> str:
    best = scores[0]
    label = "/".join(c.value for c in colors)
    fmts = ratings.formats_present if ratings else []
    if fmts:
        signal = f"grounded in 17Lands win-rates (best per card, from: {', '.join(fmts)})"
    else:
        signal = "using rarity + mechanic heuristics (no 17Lands win-rates for this set yet)"
    return (
        f"Build {label}: it has the strongest playable core in the pool "
        f"({best.playable_count} castable spells, {best.bomb_count} bomb(s), "
        f"{best.removal_count} removal, {best.creature_count} creatures in the top 23). "
        f"Card power was ranked {signal}."
    )


class SealedPipeline:
    def __init__(self, repository: CardRepository, settings: Settings,
                 ratings: RatingsIndex | None = None, llm: LLM | None = None,
                 use_llm: bool = False) -> None:
        self._repo = repository
        self._settings = settings
        self._ratings = ratings
        self._llm = llm
        self._use_llm = use_llm

    def run(self, parsed: ParsedPool, guidance: str = "") -> SealedResult:
        cost_log: list[CostEntry] = []

        pool = SealedEnrichment(self._repo, self._ratings).run(parsed, self._settings.default_set)
        cost_log.append(CostEntry(agent="enrichment", model="deterministic"))

        scores = score_color_pairs(pool)
        cost_log.append(CostEntry(agent="colorpairs", model="deterministic"))

        if self._use_llm and self._llm is not None:
            build, cost = SealedDeckBuilderAgent(self._llm, self._settings.model_strong).run(
                pool, scores, guidance
            )
            cost_log.append(cost)
            colors = build.colors or best_colors(scores)
            deck = assemble_deck(pool, colors, build.maindeck, build.rationale)
            return SealedResult(
                pool=pool, colorpair_scores=scores, chosen_colors=colors, deck=deck,
                cost_log=cost_log, built_by="ai", synergies=build.synergies,
            )

        colors = best_colors(scores)
        rationale = _rationale(pool, scores, colors, self._ratings)
        deck = build_deck(pool, colors, rationale)
        cost_log.append(CostEntry(agent="deckbuilder", model="deterministic"))
        return SealedResult(
            pool=pool, colorpair_scores=scores, chosen_colors=colors, deck=deck,
            cost_log=cost_log, built_by="deterministic",
        )


def ai_available() -> bool:
    """True when an Anthropic API key is configured (so the AI build is possible)."""
    return bool(get_secrets().anthropic_api_key)


def load_ratings(settings: Settings, *, reload: bool = False) -> RatingsIndex | None:
    """Build the per-card 17Lands ratings index for the set (best available format per card).

    Network is used only for formats not yet cached (or reload=True); on any failure it returns
    whatever is cached, or None. Never fatal to a build.
    """
    try:
        cache = RatingsCache(settings.ratings_db_path)
        return cache.ensure_index(settings.default_set, SEALED_LADDER, reload=reload)
    except Exception:  # noqa: BLE001 - ratings are an enrichment, never fatal
        return None


def build_sealed_pipeline(
    settings: Settings | None = None,
    repository: CardRepository | None = None,
    ratings: RatingsIndex | None = None,
    use_llm: bool = False,
) -> SealedPipeline:
    """Assemble a sealed pipeline. Uses the ingested Scryfall store if present, else the stub.

    When `use_llm` is set, the AI deckbuilder drives the build. It uses the real Anthropic backend
    if a key is configured; otherwise it falls back to the zero-cost mock intelligence.
    """
    settings = settings or get_settings()
    if repository is None:
        repository = (
            SqliteCardRepository(settings.db_path)
            if Path(settings.db_path).exists()
            else StubCardRepository()
        )
    llm = None
    if use_llm:
        backend = "anthropic" if ai_available() else "mock"
        llm = build_llm(settings.model_copy(update={"llm_backend": backend}), HANDLERS)
    return SealedPipeline(repository, settings, ratings, llm=llm, use_llm=use_llm)
