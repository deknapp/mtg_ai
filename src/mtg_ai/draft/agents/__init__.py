"""The draft agent network. Each agent has a single responsibility and a typed interface."""

from .archetype import ArchetypeAgent
from .enrichment import EnrichmentAgent
from .evaluation import EvaluationAgent
from .extraction import ExtractionAgent
from .synthesis import SynthesisAgent

__all__ = [
    "ExtractionAgent",
    "EnrichmentAgent",
    "ArchetypeAgent",
    "EvaluationAgent",
    "SynthesisAgent",
]
