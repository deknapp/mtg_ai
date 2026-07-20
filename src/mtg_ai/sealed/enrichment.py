"""Sealed enrichment (deterministic, no LLM).

Resolves the pool's Arena ids into real cards via the data layer and attaches each card's
17Lands rating (GIH win-rate) by id. The result is a fully-typed `Pool` the builder reasons over.
"""

from __future__ import annotations

from ..core.data import CardRepository
from .ingest_log import ParsedPool
from .models import Pool
from .ratings import RatingsResult


class SealedEnrichment:
    name = "enrichment"

    def __init__(self, repository: CardRepository, ratings: RatingsResult | None = None) -> None:
        self._repo = repository
        self._rating_by_id = ratings.by_arena_id() if ratings else {}

    def run(self, parsed: ParsedPool, set_code: str) -> Pool:
        cards = []
        unresolved: list[int] = []
        for gid in parsed.grp_ids:
            card = self._repo.lookup_by_arena_id(gid)
            if card is None:
                unresolved.append(gid)
                continue
            rating = self._rating_by_id.get(card.arena_id if card.arena_id is not None else gid)
            if rating is not None:
                card = card.model_copy(update={"rating": rating})
            cards.append(card)
        return Pool(
            set_code=parsed.set_code or set_code,
            event=parsed.event,
            cards=cards,
            unresolved_ids=unresolved,
        )
