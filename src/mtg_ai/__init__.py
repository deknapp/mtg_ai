"""mtg_ai — a general Magic: The Gathering AI toolkit.

Shared, format-agnostic machinery lives in `core` (Scryfall card data, the LLM transport with
cost-aware routing + prompt caching, config, base models). Format-specific pipelines build on
top of it:

- `sealed` — the current focus: auto-import an Arena sealed pool and build the best 40-card deck.
- `draft`  — the ported draft-pick assistant (screenshot -> next pick).
"""

__version__ = "0.1.0"
