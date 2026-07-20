"""Pipeline orchestration.

Wires the agent network into a single pass for one pick:

    extraction -> enrichment -> (archetype || evaluation) -> synthesis

The archetype and evaluation agents are independent, so they run concurrently. Model routing
is applied here: cheap tier for the narrow steps, strong tier for synthesis.
"""

from __future__ import annotations

import asyncio

from .agents import (
    ArchetypeAgent,
    EnrichmentAgent,
    EvaluationAgent,
    ExtractionAgent,
    SynthesisAgent,
)
from pathlib import Path

from ..core.config import Settings, get_settings
from ..core.data import CardRepository, SqliteCardRepository, StubCardRepository
from ..core.llm import LLM, build_llm
from ..core.models import CostEntry
from .mock_backend import HANDLERS
from .models import PipelineResult


class DraftPipeline:
    def __init__(self, llm: LLM, repository: CardRepository, settings: Settings) -> None:
        cheap, strong = settings.model_cheap, settings.model_strong
        self._extraction = ExtractionAgent(llm, cheap)
        self._enrichment = EnrichmentAgent(repository)
        self._archetype = ArchetypeAgent(llm, cheap)
        self._evaluation = EvaluationAgent(llm, cheap)
        self._synthesis = SynthesisAgent(llm, strong)

    async def run(self, image_bytes: bytes | None = None) -> PipelineResult:
        cost_log: list[CostEntry] = []

        draft_state, cost = await asyncio.to_thread(self._extraction.run, image_bytes)
        cost_log.append(cost)

        enriched = self._enrichment.run(draft_state)  # deterministic, no LLM

        # Archetype and evaluation are independent -> run them concurrently.
        (archetype, a_cost), (evaluation, e_cost) = await asyncio.gather(
            asyncio.to_thread(self._archetype.run, enriched),
            asyncio.to_thread(self._evaluation.run, enriched),
        )
        cost_log.extend([a_cost, e_cost])

        recommendation, s_cost = await asyncio.to_thread(
            self._synthesis.run, enriched, archetype, evaluation
        )
        cost_log.append(s_cost)

        return PipelineResult(
            draft_state=draft_state,
            enriched=enriched,
            archetype=archetype,
            evaluation=evaluation,
            recommendation=recommendation,
            cost_log=cost_log,
        )

    def run_sync(self, image_bytes: bytes | None = None) -> PipelineResult:
        return asyncio.run(self.run(image_bytes))


def build_pipeline(
    settings: Settings | None = None, repository: CardRepository | None = None
) -> DraftPipeline:
    """Assemble a pipeline from settings. Defaults to the mock LLM + stub data (Stage 0).

    `repository` can be injected to pin the data layer (e.g. the Stage 0 tests force the stub
    so they don't depend on whether an ingested DB happens to exist on disk). When omitted, the
    ingested Scryfall store is used if present, falling back to the built-in stub.
    """
    settings = settings or get_settings()
    llm = build_llm(settings, HANDLERS)
    if repository is None:
        # The mock backend's canned draft references the built-in stub cards, so pair it with
        # the stub for a coherent offline demo (real facts on every card, no API key). The real
        # backend uses the ingested Scryfall store when present.
        if settings.llm_backend == "mock":
            repository = StubCardRepository()
        elif Path(settings.db_path).exists():
            repository = SqliteCardRepository(settings.db_path)
        else:
            repository = StubCardRepository()
    return DraftPipeline(llm, repository, settings)
