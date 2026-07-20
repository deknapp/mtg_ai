# MTG Arena Draft Assistant

An agentic assistant that looks at a screenshot of an in-progress **Magic: The Gathering
Arena** draft — the cards you've picked so far plus the current pack — and recommends your
next pick, with a short, readable rationale.

The recommendation is produced by a **network of specialized agents**, each doing one narrow
job, orchestrated into a single pipeline. A web interface lets you upload or paste a
screenshot and see the recommended pick, ranked alternatives, and the reasoning behind it.

> This is a portfolio project. It's built to show real competence in multi-agent
> orchestration, multimodal extraction, RAG over a real dataset, cost-aware model routing,
> and a polished, opinionated web UI — with a clean architecture and commit history.

---

## What it does

1. You paste or upload a screenshot of your current Arena draft.
2. A **vision/extraction agent** reads the picked cards and the current pack into a typed,
   structured draft state.
3. A deterministic **enrichment** step joins every card name against a local **Scryfall**
   database — types, colors, mana cost, rules text, ratings — so all card facts are grounded
   in real data, not the model's memory.
4. An **archetype/color agent** reads what your deck is becoming (color commitment, open
   lanes, curve gaps) while a **card-evaluation agent** ranks the pack on raw power and limited
   signal. These run in parallel.
5. A **synthesis agent** weighs power vs. deck fit vs. signal and produces the final pick plus
   a 2–3 sentence rationale.
6. The web UI renders the recommendation — and can reveal each agent's intermediate output, so
   the reasoning is fully inspectable.

## Architecture

```
screenshot
   │
   ▼
[Vision / Extraction Agent]  ── multimodal LLM ──▶  structured draft state:
   │                                                 { picked: [...], pack: [...] }
   ▼
[Card Enrichment]  ── deterministic, no LLM ──▶  join names against local Scryfall data:
   │                                              types, colors, mana, rules text, rating
   ├──────────────┬───────────────────────────┐
   ▼              ▼                            │
[Archetype /    [Card Evaluation Agent]        │  (run in parallel)
 Color Agent]    rank pack: power + signal     │
   │              │                            │
   └──────┬───────┘                            │
          ▼                                    │
   [Synthesis Agent]  ── stronger model ──▶  final pick + ranked alternatives + rationale
          │
          ▼
   web UI renders recommendation, alternatives, and per-agent reasoning
```

### Design principles

- **Agent network, not one big prompt.** Each agent has a single responsibility and a typed
  input/output. The pipeline is legible from the code.
- **Cost-aware model routing.** Cheap model (Haiku) for narrow, high-volume steps
  (extraction, ranking); a stronger model (Sonnet, Opus only where justified) for the final
  synthesis. Tiering is a deliberate, visible design feature.
- **Prompt caching for reused context.** Card knowledge and agent system prompts are identical
  on every pick in a session, so they're cached and re-read at a large discount.
- **Grounded in real data.** Card facts come from the Scryfall dataset, not the LLM. The model
  identifies cards; the data layer supplies the facts.
- **Typed interfaces between agents.** Every inter-agent message is a Pydantic model, so the
  whole pipeline is inspectable and testable.

## Tech stack

| Layer      | Choice                                                        |
|------------|--------------------------------------------------------------|
| Backend    | Python 3.11+, FastAPI, async, Pydantic-typed I/O             |
| Agents     | Anthropic API with per-step model routing + prompt caching   |
| Data       | Scryfall bulk data ingested into SQLite (behind a repository interface) |
| Frontend   | TypeScript + React + Vite                                    |
| Testing    | pytest, with a mocked LLM so the pipeline runs without spending API budget |

## The interface

The UI is derived from MTG's own visual world rather than a generic dashboard. Its signature
idea: **the interface takes on the color identity of the deck you're drafting** — as your
picks commit to colors in the WUBRG system, the palette shifts to match. The hero is always
the recommended card and its rationale; each agent's intermediate reasoning is available
through progressive disclosure.

## Data sources

- **[Scryfall bulk data](https://scryfall.com/docs/api/bulk-data)** — the full card database,
  updated daily and free to use. This is the card-knowledge layer.
- **17Lands** — public limited-format statistics (pick order, win rates by card), used to
  ground the evaluation agent in real draft signal.

This is a personal analysis tool that reads a screenshot you provide. It does not automate,
inject into, or interact with the Arena client.

## Getting started

```bash
# backend
cp .env.example .env          # add your Anthropic API key
pip install -e .
python -m mtg_draft_assistant.ingest    # build the local Scryfall database
uvicorn mtg_draft_assistant.api:app --reload

# frontend
cd web && npm install && npm run dev
```

API keys are supplied through environment variables and are never committed. See
`.env.example` for the required configuration.

## Status

Built in staged, committable milestones — mocked end-to-end skeleton → data layer →
extraction → reasoning agents → synthesis with routing and caching → web UI → polish
(17Lands signal, per-agent "why" panel, cost dashboard, CI/CD).

## License

Personal project. Magic: The Gathering is a trademark of Wizards of the Coast; this tool is
unaffiliated and uses only freely available public data.
