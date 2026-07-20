"""Command-line entry point: run the pipeline end-to-end and print the recommendation.

With the default mock backend this runs with zero API cost on hardcoded fake draft state,
proving the wiring before any real intelligence is added (Stage 0).

    mtg-draft            # run on the built-in fake draft state (mock)
    mtg-draft path.png   # run on a screenshot (uses whatever backend .env selects)
"""

from __future__ import annotations

import sys

from ..core.config import get_settings
from .models import PipelineResult
from .pipeline import build_pipeline


def _render(result: PipelineResult) -> str:
    r = result.recommendation
    lines = [
        "",
        "=== MTG Draft Assistant ===",
        f"Picked pool : {', '.join(result.draft_state.picked)}",
        f"Current pack: {', '.join(result.draft_state.pack)}",
        "",
        f"  >>> PICK: {r.pick}",
        f"  Rationale: {r.rationale}",
        "",
        "  Alternatives:",
        *[f"    - {a.name} ({a.reason})" for a in r.alternatives],
        "",
        "  Agent trace (the 'why'):",
        f"    archetype : {result.archetype.summary}",
        "    evaluation: "
        + ", ".join(f"{s.name} p{s.power_score}/s{s.signal_score}" for s in result.evaluation.ranked),
        "",
        "  Cost log:",
        *[
            f"    {c.agent:<11} {c.model:<24} in={c.input_tokens} out={c.output_tokens} "
            f"cached={c.cached_input_tokens}"
            for c in result.cost_log
        ],
        "",
    ]
    return "\n".join(lines)


def main() -> None:
    settings = get_settings()
    image_bytes: bytes | None = None
    if len(sys.argv) > 1:
        with open(sys.argv[1], "rb") as fh:
            image_bytes = fh.read()

    pipeline = build_pipeline(settings)
    result = pipeline.run_sync(image_bytes)
    print(_render(result))


if __name__ == "__main__":
    main()
