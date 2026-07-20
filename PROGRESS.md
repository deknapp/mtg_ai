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
2. **Restructure + rename** package `mtg_draft_assistant` → `mtg_ai` with `core/ sealed/ draft/`; update pyproject, entry points, imports; get ported tests green. Commit.
3. **Arena log parser** `sealed/ingest_log.py`: auto-find Player.log → Pool (grpId→arena_id→card). Test against the captured real pool.
4. **17Lands data layer** `sealed/data_17lands.py`: fetch + cache Sealed ratings for `msh`, reload action. Verify MSH data exists.
5. **Manabase optimizer** `sealed/manabase.py`: deterministic land split + source-count feasibility (Karsten thresholds). Unit-tested.
6. **Sealed agents**: evaluation (17Lands-grounded), color-pair scorer (all 10 pairs), deckbuilder (optimizer + LLM synergy/rationale). Mock-first.
7. **Sealed pipeline** wiring; CLI path end-to-end on the real pool (mock LLM, no cost).
8. **Web UI**: decklist hero + curve + manabase + color-pair reasoning + agent trace; keep color-identity signature. One-command launch + `run.command`.
9. **Real-model validation** on the live pool (Nathan opts in; do not spend API $ without ok).
10. **README** as a portfolio artifact (general toolkit, sealed-first).

## NEED FROM USER
1. ✅ DONE — Arena Detailed Logs enabled + MSH sealed pool captured.
2. (Later) Opt-in before any **real** LLM/API spend; verify 17Lands has MSH data when we go online.

## Next action
- TODO #2: restructure/rename `mtg_draft_assistant` → `mtg_ai` (`core/ sealed/ draft/`), get tests
  green, first commit. No user input needed.
