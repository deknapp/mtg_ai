"""Sealed pipeline orchestration.

    Arena log (ParsedPool) -> enrichment -> color-pair scoring -> deck build

Color choice, selection, and the manabase are deterministic (cheap, inspectable, free). The
17Lands ratings that ground selection are fetched+cached once. An LLM synergy/rationale pass is
a future hook; today the rationale is generated deterministically from the build's own numbers.
"""

from __future__ import annotations

from pathlib import Path

from ..core.config import Settings, get_settings
from ..core.data import CardRepository, SqliteCardRepository, StubCardRepository
from ..core.models import Color, CostEntry
from .build import best_colors, build_deck, score_color_pairs
from .enrichment import SealedEnrichment
from .ingest_log import ParsedPool
from .models import ColorPairScore, Pool, SealedResult
from .ratings import RatingsCache, RatingsResult


def _rationale(pool: Pool, scores: list[ColorPairScore], colors: list[Color],
               ratings: RatingsResult | None) -> str:
    best = scores[0]
    label = "/".join(c.value for c in colors)
    if ratings and ratings.usable:
        src = ratings.source_format
        signal = (
            f"grounded in 17Lands {src} win-rates"
            + (" (sealed data not published yet, so draft data stands in)"
               if src != "Sealed" else "")
        )
    else:
        signal = "using rarity + mechanic heuristics (no 17Lands signal for this set yet)"
    return (
        f"Build {label}: it has the strongest playable core in the pool "
        f"({best.playable_count} castable spells, {best.bomb_count} bomb(s), "
        f"{best.removal_count} removal, {best.creature_count} creatures in the top 23). "
        f"Card power was ranked {signal}."
    )


class SealedPipeline:
    def __init__(self, repository: CardRepository, settings: Settings,
                 ratings: RatingsResult | None = None) -> None:
        self._repo = repository
        self._settings = settings
        self._ratings = ratings

    def run(self, parsed: ParsedPool) -> SealedResult:
        cost_log: list[CostEntry] = []

        pool = SealedEnrichment(self._repo, self._ratings).run(parsed, self._settings.default_set)
        cost_log.append(CostEntry(agent="enrichment", model="deterministic"))

        scores = score_color_pairs(pool)
        cost_log.append(CostEntry(agent="colorpairs", model="deterministic"))

        colors = best_colors(scores)
        rationale = _rationale(pool, scores, colors, self._ratings)
        deck = build_deck(pool, colors, rationale)
        cost_log.append(CostEntry(agent="deckbuilder", model="deterministic"))

        return SealedResult(
            pool=pool,
            colorpair_scores=scores,
            chosen_colors=colors,
            deck=deck,
            cost_log=cost_log,
        )


def load_ratings(settings: Settings, *, reload: bool = False) -> RatingsResult | None:
    """Ensure 17Lands ratings for the configured set are cached, then return them.

    Uses the network only when the needed data isn't cached yet (or reload=True); on any failure
    (offline, rate-limited) it returns whatever is cached, or None.
    """
    try:
        cache = RatingsCache(settings.ratings_db_path)
        result = cache.ensure(settings.default_set, "Sealed", reload=reload)
        return result
    except Exception:  # noqa: BLE001 - ratings are an enrichment, never fatal to a build
        return None


def build_sealed_pipeline(
    settings: Settings | None = None,
    repository: CardRepository | None = None,
    ratings: RatingsResult | None = None,
) -> SealedPipeline:
    """Assemble a sealed pipeline. Uses the ingested Scryfall store if present, else the stub."""
    settings = settings or get_settings()
    if repository is None:
        repository = (
            SqliteCardRepository(settings.db_path)
            if Path(settings.db_path).exists()
            else StubCardRepository()
        )
    return SealedPipeline(repository, settings, ratings)
