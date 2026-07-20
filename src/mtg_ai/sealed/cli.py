"""Command-line entry point for the sealed builder: `mtg-sealed`.

Auto-finds your MTG Arena log, reads the sealed pool, and prints the recommended 40-card deck.

    mtg-sealed                 # auto-find the Arena log, build from your current sealed pool
    mtg-sealed --reload        # re-fetch 17Lands data first
    mtg-sealed --log PATH      # read a specific Player.log
    mtg-sealed --fixture PATH  # build from a saved pool fixture (offline demo/testing)

Zero API cost: color choice, selection, and the manabase are deterministic; 17Lands ratings are
cached locally.
"""

from __future__ import annotations

import argparse
import sys

from ..core.config import get_settings
from .ingest_log import ArenaLogError, load_pool, load_pool_fixture
from .models import SealedResult
from .pipeline import build_sealed_pipeline, load_ratings

_COLOR_NAMES = {"W": "White", "U": "Blue", "B": "Black", "R": "Red", "G": "Green"}
_SRC_SHORT = {"ArenaDirect_Sealed": "event", "Sealed": "sealed", "TradSealed": "sealed",
              "PremierDraft": "draft", "TradDraft": "draft", "QuickDraft": "draft"}


def _rating_str(dc) -> str:
    """A card's win-rate with its source tag, e.g. '56.6% event', or a bomb/no-data marker."""
    if dc.rating is not None:
        src = _SRC_SHORT.get(dc.rating_source or "", dc.rating_source or "")
        return f"{dc.rating*100:4.1f}% {src:<6}"
    if (dc.rarity or "").lower() in {"rare", "mythic"}:
        return "  --   BOMB? "
    return "  --        "


def _render(result: SealedResult) -> str:
    deck = result.deck
    colors = "/".join(_COLOR_NAMES[c.value] for c in result.chosen_colors)
    lines = [
        "",
        "══════════════════════════════════════════════════",
        "  MTG AI — Sealed Deck Builder",
        "══════════════════════════════════════════════════",
        f"  Pool      : {len(result.pool.cards)} cards"
        + (f"  ({result.pool.event})" if result.pool.event else ""),
        f"  Colors    : {colors}",
        "",
        f"  >>> {deck.total_cards}-card deck  "
        f"({len(deck.spells)} spells + {deck.manabase.total_lands} lands)",
        f"  Creatures {deck.creatures} | Removal {deck.removal} | Bombs {len(deck.bombs)}",
        "",
        f"  Built by : {'AI (reasoned)' if result.built_by == 'ai' else 'deterministic optimizer'}",
        "",
        "  Rationale:",
        f"    {deck.rationale}",
    ]
    if result.synergies:
        lines.append("")
        lines.append("  Synergies:")
        lines += [f"    - {s}" for s in result.synergies]
    lines += ["", "  Top color pairs considered:"]
    for s in result.colorpair_scores[:4]:
        lines.append(
            f"    {s.label:>2}  score {s.deck_score:6.2f}  "
            f"| {s.playable_count:2d} playable  {s.bomb_count} bomb  "
            f"{s.removal_count} removal  {s.creature_count} creatures"
        )

    lines += ["", "  ── Spells (by curve) ──   [★ bomb  ✜ removal | win-rate source: "
              "event=your Arena Direct sealed, sealed=generic, draft=proxy] ──"]
    for dc in deck.spells:
        tag = "★" if dc.is_bomb else ("✜" if dc.role == "removal" else " ")
        lines.append(f"    {tag} {int(dc.cmc)}  {dc.name:<32} {_rating_str(dc)}  {dc.rarity or ''}")

    lines += ["", "  ── Manabase ──"]
    for land, n in deck.manabase.lands.items():
        lines.append(f"    {n:>2}x {land}")
    lines.append("    curve: " + "  ".join(f"{k}:{v}" for k, v in deck.curve.items()))
    if deck.manabase.splash_colors:
        lines.append("    splash: " + "/".join(c.value for c in deck.manabase.splash_colors))
    feasible = "✓ feasible" if deck.manabase.feasible else "⚠ tight"
    lines.append(f"    mana: {feasible}")
    for note in deck.manabase.notes:
        lines.append(f"      - {note}")

    if deck.sideboard_highlights:
        lines += ["", "  ── Next best (sideboard) ──"]
        for dc in deck.sideboard_highlights:
            lines.append(f"    {dc.name:<32} {_rating_str(dc)}  {dc.rarity or ''}")

    lines += ["", "  Pipeline:"]
    for c in result.cost_log:
        lines.append(f"    {c.agent:<12} {c.model}")
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the best sealed deck from your Arena pool.")
    parser.add_argument("--log", default=None, help="Path to a specific Arena Player.log.")
    parser.add_argument("--fixture", default=None, help="Build from a saved pool JSON fixture.")
    parser.add_argument("--reload", action="store_true", help="Re-fetch 17Lands data first.")
    parser.add_argument("--ai", action="store_true",
                        help="Let the AI reason over the build (uses your Anthropic API key).")
    ns = parser.parse_args()

    settings = get_settings()
    try:
        parsed = load_pool_fixture(ns.fixture) if ns.fixture else load_pool(ns.log)
    except ArenaLogError as e:
        print(f"\n{e}\n", file=sys.stderr)
        sys.exit(1)

    if parsed.set_code:
        settings.default_set = parsed.set_code

    ratings = load_ratings(settings, reload=ns.reload)
    pipeline = build_sealed_pipeline(settings, ratings=ratings, use_llm=ns.ai)
    if ns.ai:
        print("  Reasoning over your pool with the AI deckbuilder…", file=sys.stderr)
    result = pipeline.run(parsed)
    print(_render(result))


if __name__ == "__main__":
    main()
