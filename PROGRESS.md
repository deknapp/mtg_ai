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

### Quantitative-data upgrade (2026-07-19, commit `3341a06`) — DONE
- **Per-card 17Lands ladder** (`ratings.py`): default `ArenaDirect_Sealed` (the actual event),
  per-card fallback → Sealed → PremierDraft, each number tagged with source + game-count.
- **AI scaffold** (`deckbuilder_llm.py`): color-pair scores, source-tagged win-rates, fixing lands
  + produced colors, explicit BOMB flags, sealed framing — all in the prompt.
- **Splash-aware Karsten manabase** (`manabase.py` + `docs/karsten-manabase.md`): counts pool
  fixing lands as sources (Scryfall `produced_mana` now ingested), main/splash classification,
  Karsten 40-card thresholds (late single-pip splash ≈ 6 sources).
- **Provenance** in CLI + UI (event/sealed/draft/no-data tags, splash + fixing shown). Dropped ALSA.

### KEY 17Lands data findings (don't re-derive — this cost hours)
- MSH released on Arena **2026-06-23** (a month ago), NOT July 17 — that date in the event name is
  the Arena Direct event, not the set release. Verified via `https://www.17lands.com/data/filters`
  (`start_dates.MSH`).
- The live `card_ratings/data` endpoint (what we + every draft tool use) serves a **rolling/scoped
  view, not full all-time** — proven: FIN (huge set) returns ~135 games / 0 win-rates; `start_date`
  and `time_period` params are **ignored**. So MSH rares/bombs have **no win-rate in any format yet**.
- Canonical full-history source = **17Lands S3 public datasets**:
  `https://17lands-public.s3.amazonaws.com/analysis_data/{game_data,draft_data}/..._public.{SET}.{FMT}.csv.gz`
  (raw per-game rows you aggregate). **MSH game_data is NOT published yet** (only draft_data, 57.6MB,
  updated Jul 7) — verified game_data exists for WOE/DSK but 403s for MSH. So all-time GIHWR for MSH
  bombs genuinely isn't available anywhere until 17Lands posts it. `SEALED_LADDER` is ordered so an
  S3 aggregator can be added on top later. Community reference tool: `bstaple1/MTGA_Draft_17Lands`.

### Polish backlog (nice-to-have)
- Curve card names truncate hard in narrow columns (worse now with source tags) — add a tooltip / full name.
- Removal detection regex may under-count; revisit with set mechanics.
- Manabase includes off-color duals (e.g. R/W land in WU) as a source; doesn't model tapped lands / ramp fixing.
- Deferred: S3 game-data download+aggregation pipeline (build when 17Lands posts MSH game data).

### Known small items / polish
- 2 of 84 pool ids (105176, 105182) don't resolve on Scryfall's arena endpoint (basic lands / art
  variants) — correctly excluded; we generate basics. Non-issue.
- Removal detection is a regex heuristic — may under-count; fine for v1, revisit with set mechanics.
- Sealed win-rates on 17Lands are still empty for MSH; PremierDraft fallback is active. Re-check later.

### Pool picker + "newest not largest" fix (2026-07-20) — DONE
- **Bug:** the log holds several `CardPool` arrays — the complete pool is re-emitted, and shrinking
  copies are logged as cards move to the deck. `parse_pool` did `max(pools, key=len)`, which on a
  size tie returns the *first* complete pool. With two 84-card pools in the log (two sealed sit-downs)
  it always served the **older** one — the reported "it's using the old pool" symptom.
- **Fix:** `ingest_log.list_pools(text)` returns every *distinct complete* pool (keeps only
  max-length arrays → drops fragments regardless of set, de-dupes by contents), newest-first, each
  tagged with wall-clock timestamp + event. `parse_pool` now returns the most-recent pool.
- **API:** `GET /api/sealed/pools` lists them (timestamp/event/set/count + a few highest-rarity
  card names for recognition); `POST /api/sealed/build` builds the exact selected pool by grp_ids.
- **UI:** a **Pool** dropdown in the header (defaults to ★ latest); Quick build / Build with AI use
  the selection; a note shows how many pools were found + which is selected.
- Tests: +regression (`most_recent_full_pool_not_the_first`) + `list_pools` dedupe/order. 34 pass.

### AI guidance / "redo with my opinion" (2026-07-20) — DONE
- Free-text steer for the AI build threaded end-to-end: web input → API → pipeline →
  `deckbuilder_llm`. `SealedDeckBuilderAgent.run(pool, scores, guidance)` appends a **PLAYER
  GUIDANCE** block to the user prompt (honored over the data-driven default where the pool allows;
  deterministic manabase still enforces castability, model explains any tradeoff).
- API: `guidance` is a query param on `GET /api/sealed/{demo,build}` and a body field on
  `POST /api/sealed/build`. Only applied when `ai=true` (deterministic build ignores it).
- UI: a **"Tell the AI"** input bar under the header (Enter = build); header AI button relabels to
  **"Redo with AI"** after an AI build, so iterating on the same pool with new input is one click.
- Test: `test_guidance_is_passed_into_the_ai_prompt` (spy LLM asserts the steer reaches the prompt,
  and that no guidance section leaks when empty). 35 tests pass.

### Self-healing server spinup (2026-07-20) — DONE
- Closing the Terminal can orphan uvicorn (it keeps holding port 8000), so the next `run.command`
  used to fail with `address already in use`. `serve.py` now self-heals on startup:
  - Port free → serve on 8000.
  - Port held by a **leftover mtg_ai server** (identified via `GET /api/sealed/status`) → SIGTERM→
    SIGKILL it (`_reclaim_port`), then reuse 8000 — so restarts always work.
  - Port held by **something unrelated** → leave it alone, serve on the next free port (8001–8010).
  - No port free in range → clear error with the manual `lsof -ti:8000 | xargs kill` hint.
- Verified end-to-end: double-launch (no stop between) → 2nd launch reclaims 8000 (PID changes),
  never falls back to 8001; foreign occupant → correctly moves to 8001.

### Readable deck visualizer + no-cache HTML (2026-07-20) — DONE
- The "deck, by curve" columns clipped card names (6 narrow cols, `.dc-name` was nowrap+ellipsis →
  "Iron M…"). Now: min column width 116px (row scrolls x on tiny windows), names **wrap fully**
  (`overflow-wrap:anywhere`), and the win-rate moved to its own muted line under the name.
- `api.py` middleware sets `Cache-Control: no-store` on the HTML shell only (hashed JS/CSS still
  cache) — fixes the recurring "I rebuilt but the browser shows the old page" stale-tab problem.
  (A server already running from before this change still needs one hard-reload; restarts don't.)

### Three-color/splash assessment + Iterate-vs-Fresh AI (2026-07-20) — DONE
- **3-color splash intelligence.** `build.assess_splashes(pool, bases)` evaluates, for the top
  2-color bases, each third-color splash: the off-color cards worth splashing (bombs / cards better
  than the base's weakest non-bomb), net power gain, and pool fixing-land count for that color. A
  splash is *light* (≤3 cards) and only surfaces with a bomb or clear gain — mirroring real sealed.
  Fed to the AI prompt as a **THREE-COLOR / SPLASH OPPORTUNITIES** block ("prefer 3-color when a
  splash adds a bomb AND has ~3+ fixing sources") and shown in a new UI panel. `SealedResult` now
  carries `splash_options`. Fixes "the best build was clearly 3 colors and the AI missed it."
- **Iterate vs Start Fresh.** The single AI button split into **✦ Start Fresh with AI** (from
  scratch) and **⟳ Iterate with AI** (feeds the current build back via `PriorBuild` so the model
  *revises* it per the guidance instead of re-deriving). POST body gained `prior`; agent prompt
  gained a YOUR-PREVIOUS-BUILD section. Guidance-box Enter = iterate when a deck exists, else fresh.
- Tests: `assess_splashes` finds a bomb off fixing; splash+prior sections reach the prompt. 37 pass.

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
