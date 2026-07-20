# mtg_ai

A general **Magic: The Gathering AI toolkit**. The current focus is a **Sealed deck builder**
that auto-imports your MTG Arena pool and builds the best legal 40-card deck for it — color
choice, card selection, and a mana-feasible manabase — grounded in real data, not model memory.

> **Try it (no setup beyond an ingest):**
> ```bash
> uv run python -m mtg_ai.core.ingest --set msh          # build the card DB for the set
> uv run mtg-sealed --fixture tests/fixtures/sealed_pool_msh.json   # build from a saved pool
> uv run mtg-sealed                                        # …or read your live Arena pool
> ```

---

## What it does (sealed)

```
MTG Arena log ─▶ pool import ─▶ enrichment ─▶ color-pair scoring ─▶ deck build ─▶ 40-card deck
 (Player.log)    (grpId→card)   (Scryfall +   (all 10 pairs)       (selection +   + curve
                                 17Lands)                            manabase +     + manabase
                                                                     bombs)         + rationale
```

1. **Auto-import the pool.** MTG Arena writes your sealed pool to its local log as card ids
   (`grpId`s). We find the log, read the pool, and map each `grpId` to a real card via Scryfall's
   `arena_id` — **no screenshots, no OCR, no typing.** (Requires Arena's *Detailed Logs (Plugin
   Support)* setting; the tool tells you exactly what to do if it's off.)
2. **Ground every card in real data.** Card facts come from a local **Scryfall** store; card
   *power* comes from **17Lands** games-in-hand win-rates, cached locally.
3. **Choose colors objectively.** Score all ten two-color pairs by the strength of their best 23
   castable spells (bombs weighted up) and pick the strongest.
4. **Build a deck you can actually cast.** Select 23 spells (bombs prioritized, with a creature
   floor), then optimize a 17-land manabase and check each color against a **Frank-Karsten-style
   "sources needed to cast on curve"** threshold — so the recommendation is legal *and* castable.

### Design objectives (from the brief)
- **A — Mana feasibility.** A deterministic manabase optimizer + source-count check. If a color's
  requirements can't be supported by a sane 17-land split, the deck is flagged, not silently shipped.
- **B — Bombs.** High-rarity, high-win-rate cards are detected and prioritized into the build, and
  pull color choice toward them.
- **C — Synergy.** 17Lands aggregate data is context-independent, so it does **not** encode pairwise
  synergy; v1 uses composition/mechanic heuristics, and an LLM synergy pass is the next layer
  (deliberately honest about what the data can and can't do).

## Architecture

Shared, format-agnostic machinery in `core`; format pipelines on top:

```
src/mtg_ai/
  core/     config · data (Scryfall SQLite, name + arena_id lookups) · ingest · llm · models
  sealed/   ingest_log · ratings (17Lands cache) · enrichment · scoring · manabase · build · pipeline · cli
  draft/    the ported draft-pick assistant (screenshot → next pick)
  api.py · serve.py     one-command local web app
```

Portfolio-relevant choices:
- **Cost-aware by construction.** The expensive part of sealed (color choice, selection, manabase)
  is *deterministic optimization* — free and fully inspectable. An LLM is reserved for synergy
  judgement and the readable rationale, behind the same routed/cached transport the draft
  assistant uses (Haiku for narrow steps, Sonnet for synthesis, system-prompt caching).
- **Data spine keyed by id.** Arena log, Scryfall, and 17Lands all join on `arena_id`/`mtga_id` —
  no fuzzy name matching in the sealed path.
- **Graceful data fallback.** A freshly released set has no 17Lands *sealed* win-rates yet, so the
  ratings layer falls back to the set's *draft* data (`Sealed → PremierDraft → …`) and, failing
  that, to rarity/mechanic heuristics. The build always runs.
- **Typed interfaces, mock-first.** Every stage passes Pydantic models; the whole pipeline runs
  offline with zero API cost, which is also how the tests exercise it.

## Data sources
- **Scryfall** bulk/set data (free, within their guidelines) → local SQLite card store, carrying
  `arena_id`. Build it with `python -m mtg_ai.core.ingest --set <code>`.
- **17Lands** public card-ratings per `(set, format)` → local SQLite cache. Reload with
  `mtg-sealed --reload`. Sealed data used when available; draft data as the fallback signal.

## Running
```bash
uv venv -p 3.12 && uv pip install -e ".[dev]"
uv run python -m mtg_ai.core.ingest --set msh     # one-time card DB for the set
uv run mtg-sealed                                  # build from your current Arena sealed pool
uv run pytest -q                                   # 26 tests, all offline
```
Enabling the Arena pool import (one-time): **Arena → Settings → Account → "Detailed Logs (Plugin
Support)"**, fully quit and reopen Arena, then open your sealed event.

## Status
Sealed pipeline is complete and validated end-to-end on a real 84-card Marvel Super Heroes pool
(→ a legal, mana-feasible W/U deck). See `PROGRESS.md` for the live status, decisions, and roadmap
(web UI, LLM synergy pass). The draft-pick assistant is ported and kept working atop `core`.

## Legal / ToS
A personal analysis tool that reads a pool from a log the user already has. Scryfall and 17Lands
data are used within their public guidelines. No automation of or injection into the Arena client.
