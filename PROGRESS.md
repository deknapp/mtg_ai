# mtg_ai — Context & Progress

**Purpose of this file:** the living source of truth for where this project is, what's decided, and
what's left. Intended for the coding agent (Claude) to read at the start of every session and for
Nathan + Claude to update as work lands. Keep it current — update it at each milestone. This file
IS committed to the repo (unlike the draft project's external PROGRESS.md).

---

## What this is

`mtg_ai` — a general MTG AI toolkit, seeded from the working `mtg_draft_assistant`. **Current focus:
a Sealed deck builder** that auto-imports the player's Arena pool and builds the best legal 40-card
deck. The draft assistant is ported alongside but is not the current focus.

Portfolio project (hiring-manager audience): the win is legible multi-agent architecture, a real
data pipeline (Scryfall + 17Lands), cost-aware model routing, a deterministic mana-optimization
core, and a polished, easy-to-run Mac app. See the spec/design in `~/Desktop/projects/mtg_claude_context/`.

## Locations
- **Repo (local):** `~/Desktop/projects/mtg_ai`
- **Repo (GitHub, PRIVATE):** https://github.com/deknapp/mtg_ai  (account: `deknapp`)
- **Seed repo:** `~/Desktop/projects/mtg_draft_assistant` (private, working, stages 0–5 done)
- **Context docs (NOT in repo):** `~/Desktop/projects/mtg_claude_context/` — spec, frontend proposal.

## Working agreement (from Nathan)
- **Focus set: Marvel Super Heroes (`msh`)** — same as the draft repo. Scope card DB + 17Lands to it.
- Give **manual steps (things Nathan does) one at a time**, wait for confirmation between each.
- Do the steps that **don't need Nathan's input first**; keep a running "NEED FROM USER" list below.
- **No parallel-agent swarms / subagents** — work sequentially, main agent only.
- Commit + push at every milestone so no work is lost. Keep this file current.
- Make it **easy to run and visual** on a Mac.

## Decisions locked
- **Visibility:** private. **Git history:** fresh (draft repo history not carried over).
- **Pool input:** **auto-find and parse the Arena `Player.log`** — no pasting, no screenshots.
  UX goal: open the app → it finds your sealed pool → it builds your deck.
- **Easy-run app:** one-command local web app that opens the browser (inherit `serve.py`), plus a
  double-clickable `run.command`. No native `.app` bundle in v1.
- **17Lands:** fetch card-ratings per `(set, format=Sealed)`, cache locally in SQLite behind the
  data-layer interface, with a **reload** action (CLI flag + app button). **Fallback ladder if MSH
  Sealed rows don't exist:** (1) use the set's **Limited/draft** data (PremierDraft/QuickDraft) and
  infer from that — card power carries over well between sealed and draft; (2) only then drop to
  Scryfall rarity + LLM heuristics.
- **Deckbuilder = hybrid** (deterministic optimizer + LLM):
  - **A. Mana feasibility** — deterministic. Land split + color-source counts checked against
    Karsten-style "sources to cast on curve" thresholds; penalize/re-color infeasible builds.
  - **B. Bomb rares** — include high **GIH WR** + high-rarity cards (17Lands), LLM-confirmed.
  - **C. Synergy** — NOT from 17Lands aggregate data (context-independent). Comes from rules-text/
    mechanic heuristics + the LLM synthesis agent. 17Lands color-pair/archetype WR guides *color*
    choice, not card pairs. Data-driven pairwise synergy (game-data CSVs) is a later, optional stage.

## Architecture plan
Shared core + format modules:
```
src/mtg_ai/
  core/     config, data (Scryfall SQLite + repo iface), ingest, llm (routing+cache), models (Card/Color/Cost)
  sealed/   models (Pool, DeckList, ColorPairScore), ingest_log (Arena Player.log -> Pool),
            data_17lands (fetch+cache ratings), agents/ (evaluation, color_pairs, deckbuilder),
            manabase (deterministic optimizer), pipeline
  draft/    ported draft agents + pipeline (not the current focus)
  api, cli, serve  (one-command app)
web/        React+Vite UI; hero = the built decklist; keep the WUBRG color-identity signature
```
Sealed pipeline: `log parse -> enrichment (Scryfall + 17Lands) -> (evaluate pool || score 10 color
pairs) -> deckbuilder (manabase optimizer + LLM synergy/rationale) -> DeckList`.

## 17Lands notes (verify when online)
- Endpoint shape: `…/card_ratings/data?expansion=<SET>&format=Sealed` → per-card rows incl.
  `ever_drawn_win_rate` (GIH WR), `avg_seen` (ALSA), `drawn_improvement_win_rate` (IWD), rarity, color.
- **Must verify:** real MSH expansion code on 17Lands + that Sealed rows exist. Join to Scryfall by name.
- Deep pairwise synergy would require 17Lands public **game-data CSVs** (co-occurrence WR) — later.

## Arena log notes
- Path: `~/Library/Logs/Wizards Of The Coast/MTGA/Player.log` (Epic install: `/Users/Shared/Epic Games/MagicTheGathering`).
- Pool card data only appears when Arena's **"Detailed Logs (Plugin Support)"** is ON. Log header
  prints `DETAILED LOGS: ENABLED/DISABLED` at boot — check that first.
- Pool cards are logged as `grpId`s → map via Scryfall `arena_id` → card. Emitted on entering the
  sealed event / deckbuilder (course request).

## Status (2026-07-19)
- [x] Private repo `deknapp/mtg_ai` created + cloned locally (empty on GitHub — nothing pushed yet).
- [x] Draft source tree copied into `mtg_ai/` (still named `mtg_draft_assistant`, NOT yet restructured).
- [x] **Arena Detailed Logs ENABLED; real MSH sealed pool captured + mapping validated end-to-end.**
  Event `ArenaDirect_MSH_Play_Sealed_20260717`, **84 cards**. `CardPool` grpIds → Scryfall `arena_id`
  → real cards confirmed live (e.g. 105048=Stark Industries Executive, all `set:msh`). Pool saved as
  fixture `tests/fixtures/sealed_pool_msh.json` (raw grpIds; logs rotate on restart, so this is our copy).
- [ ] Everything below.

## TODO (roughly in order)
1. ~~**Capture a real MSH sealed pool**~~ ✅ DONE — 84-card pool captured, mapping validated, fixture saved.
2. ~~**Restructure + rename** → `core/ sealed/ draft/`~~ ✅ DONE — committed `02e8fb5`, 15 ported tests green, draft CLI works.
3. ~~**Arena log parser** `sealed/ingest_log.py`~~ ✅ DONE — auto-find + largest-CardPool parse + actionable errors; tested.
4. ~~**17Lands data layer** `sealed/ratings.py`~~ ✅ DONE — fetch+cache+reload, Sealed→PremierDraft fallback, joins by arena_id.
5. ~~**Manabase optimizer** `sealed/manabase.py`~~ ✅ DONE — pip-proportional 17-land split + Karsten feasibility flag; tested.
6. ~~**Sealed engine** color-pair scorer + selection + deckbuilder~~ ✅ DONE — `sealed/build.py`, deterministic, bombs prioritized.
7. ~~**Sealed pipeline + `mtg-sealed` CLI**~~ ✅ DONE — validated on the real 84-card pool → legal W/U 40-card deck. Committed `9c39261`, pushed.
8. ~~**Web UI (sealed)**~~ ✅ DONE — decklist hero (parchment, color-identity), curve columns,
   manabase w/ feasibility chip, color-pair table, sideboard, pipeline. `/api/sealed/{demo,build}`
   endpoints; App is sealed-first, opens on the sample pool, "Build from my Arena pool" button.
   One-command `mtg-ai` launcher + double-click `run.command`. Built + screenshot-verified.
9. ~~**README** portfolio artifact~~ ✅ DONE — sealed-first, architecture, objectives A/B/C, data spine.
10. ~~**AI deckbuilder**~~ ✅ DONE — `sealed/deckbuilder_llm.py`: Opus 4.8 + adaptive thinking reasons
    over the whole pool (17Lands GIHWR as a guide), picks colors (2 or 3), the 23 cards, synergies,
    and bombs; deterministic manabase still enforces castability. `--ai` CLI flag, `?ai=true` API,
    "Build with AI" button + "AI reasoned" badge + synergies panel. `model_strong=claude-opus-4-8`.
    Mock-first (free offline). **Validated LIVE on the real MSH pool** → W/U artifacts, found both
    mythic bombs (Tony Stark + Ultron), explained the artifact engine, feasible mana. Committed `1c2c701`.
11. ~~**Real-model validation**~~ ✅ DONE — Nathan opted in; live Opus builds confirmed via CLI + API.

### Polish backlog (nice-to-have)
- Curve card names truncate hard in narrow columns — add a hover tooltip / full name on wider screens.
- Removal detection regex may under-count; revisit with set mechanics.
- Re-check 17Lands for MSH *Sealed* win-rates later (currently PremierDraft fallback).

### Known small items / polish
- 2 of 84 pool ids (105176, 105182) don't resolve on Scryfall's arena endpoint (basic lands / art
  variants) — correctly excluded; we generate basics. Non-issue.
- Removal detection is a regex heuristic — may under-count; fine for v1, revisit with set mechanics.
- Sealed win-rates on 17Lands are still empty for MSH; PremierDraft fallback is active. Re-check later.

## NEED FROM USER
1. ✅ DONE — Arena Detailed Logs enabled + MSH sealed pool captured.
2. (Later) Opt-in before any **real** LLM/API spend; verify 17Lands has MSH data when we go online.

## Next action
- Sealed builder is complete AND AI-enabled (Opus deckbuilder), CLI + visual web app, validated
  live on the real MSH pool. Only the polish backlog remains; nothing is blocked.
- Model routing: cheap=`claude-haiku-4-5`, strong=`claude-opus-4-8` (adaptive thinking for the AI
  build). AI uses the ANTHROPIC_API_KEY already in `.env` — every AI build spends a few cents.
- Try it now:
  - Visual app:  `uv run mtg-ai`  → click **Build with AI**   (or double-click `run.command`)
  - CLI (AI):    `uv run mtg-sealed --ai`     ·  free deterministic: drop `--ai`
  - Sample/offline: `uv run mtg-sealed --ai --fixture tests/fixtures/sealed_pool_msh.json`
