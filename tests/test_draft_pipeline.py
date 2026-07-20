"""Stage 0 wiring tests: the pipeline runs end-to-end on the mock backend with no API calls."""

from __future__ import annotations

from mtg_ai.draft.agents import EnrichmentAgent
from mtg_ai.core.config import Settings
from mtg_ai.core.data import StubCardRepository
from mtg_ai.core.models import Color
from mtg_ai.draft.models import DraftState
from mtg_ai.draft.pipeline import build_pipeline


def _mock_settings() -> Settings:
    return Settings(llm_backend="mock")


def _mock_pipeline():
    # Pin the stub data layer so these Stage 0 tests are independent of any ingested DB on disk.
    return build_pipeline(_mock_settings(), repository=StubCardRepository())


def test_pipeline_runs_end_to_end():
    result = _mock_pipeline().run_sync()
    # Every card name resolved against the stub data layer.
    assert all(not c.unresolved for c in result.enriched.pack)
    # The deck read from the fake picks is red-black (Lightning Strike, Goblin Guide, Duress).
    assert Color.RED in result.archetype.committed_colors
    assert Color.BLACK in result.archetype.committed_colors


def test_recommends_best_on_color_card():
    # Murder (on-color removal, rating 7.5) should beat off-color Serra Angel (7.0).
    result = _mock_pipeline().run_sync()
    assert result.recommendation.pick == "Murder"
    assert result.recommendation.rationale
    assert len(result.recommendation.alternatives) >= 1


def test_cost_log_covers_every_llm_agent():
    result = _mock_pipeline().run_sync()
    agents = {c.agent for c in result.cost_log}
    assert agents == {"extraction", "archetype", "evaluation", "synthesis"}
    # Synthesis is routed to the strong tier; the narrow steps to the cheap tier.
    by_agent = {c.agent: c.model for c in result.cost_log}
    assert "opus" in by_agent["synthesis"]      # strong tier
    assert "haiku" in by_agent["extraction"]    # cheap tier


def test_enrichment_flags_unknown_cards():
    enriched = EnrichmentAgent(StubCardRepository()).run(
        DraftState(picked=["Murder"], pack=["Not A Real Card"])
    )
    assert enriched.picked[0].unresolved is False
    assert enriched.pack[0].unresolved is True


def test_enrichment_fuzzy_corrects_ocr_misreads():
    # The vision agent makes OCR-style slips; enrichment should snap them back to the real card.
    enriched = EnrichmentAgent(StubCardRepository()).run(
        DraftState(picked=[], pack=["Lightnng Strike", "Llanowar Elfs", "Zzzz Nonsense"])
    )
    strike, elves, junk = enriched.pack
    assert strike.name == "Lightning Strike" and strike.unresolved is False
    assert elves.name == "Llanowar Elves" and elves.unresolved is False
    # A name too far from anything real stays flagged rather than snapping to a wrong card.
    assert junk.unresolved is True
