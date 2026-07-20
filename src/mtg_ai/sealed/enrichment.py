"""Sealed enrichment (deterministic, no LLM).

Resolves the pool's Arena ids into real cards via the data layer and attaches each card's
best-available 17Lands rating — the win rate, the format it came from, and its game count —
from the per-card RatingsIndex. The result is a fully-typed `Pool` the builder reasons over.
"""

from __future__ import annotations

from ..core.data import CardRepository
from .ingest_log import ParsedPool
from .models import Pool
from .ratings import RatingsIndex


class SealedEnrichment:
    name = "enrichment"

    def __init__(self, repository: CardRepository, ratings: RatingsIndex | None = None) -> None:
        self._repo = repository
        self._ratings = ratings

    def run(self, parsed: ParsedPool, set_code: str) -> Pool:
        cards = []
        unresolved: list[int] = []
        for gid in parsed.grp_ids:
            card = self._repo.lookup_by_arena_id(gid)
            if card is None:
                unresolved.append(gid)
                continue
            rating = self._ratings.get(card.arena_id if card.arena_id is not None else gid) \
                if self._ratings else None
            if rating is not None:
                card = card.model_copy(update={
                    "rating": rating.wr,
                    "rating_source": rating.source,
                    "rating_games": rating.games,
                })
            cards.append(card)
        return Pool(
            set_code=parsed.set_code or set_code,
            event=parsed.event,
            cards=cards,
            unresolved_ids=unresolved,
        )
