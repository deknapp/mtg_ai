"""FastAPI backend.

Exposes the draft pipeline over HTTP and, in one-command mode, serves the built React UI so
the whole thing runs as a single process on a single URL (see `serve.py` / `mtg-draft-app`).

Cost safety is built in:
- `/api/demo` ALWAYS runs the zero-cost mock backend (it's a canned showcase draft).
- `/api/recommend` runs on the mock backend by default; it only uses real models when the
  request opts in (`?live=true`) AND an ANTHROPIC_API_KEY is configured. So launching the app
  and clicking around never spends anything unless you explicitly ask for a real analysis.

    uvicorn mtg_draft_assistant.api:app --reload      # API + (if built) the UI at /
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .core.config import Settings, get_secrets
from .core.data import CardRepository, SqliteCardRepository
from .draft.models import PipelineResult
from .draft.pipeline import build_pipeline
from .sealed.ingest_log import (
    ArenaLogError,
    ParsedPool,
    detailed_logs_status,
    find_arena_log,
    list_pools,
    load_pool,
    load_pool_fixture,
)
from .sealed.models import PriorBuild, SealedResult
from .sealed.pipeline import ai_available, build_sealed_pipeline, load_ratings

# The built frontend (web/dist), if it has been produced by `npm run build`.
_DIST = Path(__file__).resolve().parents[2] / "web" / "dist"
_FIXTURE = Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "sealed_pool_msh.json"


@asynccontextmanager
async def lifespan(app: FastAPI):
    # A zero-cost mock pipeline is always available: it powers the demo and is the safe default.
    app.state.mock_pipeline = build_pipeline(Settings(llm_backend="mock"))
    # A real pipeline is built only when a key is present (constructing it makes no API call).
    app.state.live_available = bool(get_secrets().anthropic_api_key)
    app.state.live_pipeline = (
        build_pipeline(Settings(llm_backend="anthropic"))
        if app.state.live_available
        else app.state.mock_pipeline
    )
    yield


app = FastAPI(title="mtg_ai — Sealed Deck Builder + Draft Assistant", version="0.1.0", lifespan=lifespan)

# Allow the Vite dev server origin during development (harmless once the UI is served here).
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def _no_store_html(request, call_next):
    """Never let the browser cache the HTML shell, so a rebuilt UI shows up on plain reload.

    Content-hashed JS/CSS under /assets keep their default (cacheable) headers — only the HTML
    entry point is marked no-store, which is what caused "I don't see my change" stale tabs.
    """
    response = await call_next(request)
    if response.headers.get("content-type", "").startswith("text/html"):
        response.headers["Cache-Control"] = "no-store"
    return response


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/api/status")
def status() -> dict:
    """Tell the UI whether real-model analysis is available (i.e. a key is configured)."""
    return {"live_available": bool(app.state.live_available)}


@app.get("/api/demo", response_model=PipelineResult)
async def demo() -> PipelineResult:
    """Run the built-in draft on the mock backend (always free, no screenshot needed)."""
    return await app.state.mock_pipeline.run(None)


@app.post("/api/recommend", response_model=PipelineResult)
async def recommend(
    screenshot: UploadFile = File(...),
    live: bool = Query(False, description="Use real models (only if a key is configured)."),
) -> PipelineResult:
    """Run the pipeline on an uploaded draft screenshot.

    Defaults to the mock backend; uses real models only when `live=true` is requested and a key
    is available. This keeps accidental clicks free.
    """
    image_bytes = await screenshot.read()
    use_live = live and app.state.live_available
    pipeline = app.state.live_pipeline if use_live else app.state.mock_pipeline
    return await pipeline.run(image_bytes)


# --- Sealed endpoints ----------------------------------------------------------------------
# The sealed build is deterministic (no LLM), so these are always free — no live toggle needed.


def _run_sealed(
    parsed: ParsedPool,
    use_ai: bool = False,
    guidance: str = "",
    prior: PriorBuild | None = None,
) -> SealedResult:
    settings = Settings()
    if parsed.set_code:
        settings.default_set = parsed.set_code
    ratings = load_ratings(settings)  # cached; network only on first fetch
    # Guidance and the prior build only steer the AI build; the deterministic build ignores them.
    return build_sealed_pipeline(settings, ratings=ratings, use_llm=use_ai).run(
        parsed, guidance=guidance if use_ai else "", prior=prior if use_ai else None
    )


# Rarity ordering so the sample-card preview leads with the pool's bombs — the cards that best
# distinguish two same-size pools from the same event.
_RARITY_RANK = {"mythic": 4, "rare": 3, "uncommon": 2, "common": 1}


def _card_repo() -> CardRepository | None:
    """The Scryfall card DB if it's been built, else None (name previews just get skipped)."""
    db_path = Settings().db_path
    return SqliteCardRepository(db_path) if Path(db_path).exists() else None


def _sample_card_names(repo: CardRepository | None, grp_ids: list[int], limit: int = 4) -> list[str]:
    """A few notable (highest-rarity) card names from a pool, to help the user recognize it."""
    if repo is None:
        return []
    by_name: dict[str, int] = {}
    for gid in grp_ids:
        card = repo.lookup_by_arena_id(gid)
        if card and card.name not in by_name:
            by_name[card.name] = _RARITY_RANK.get((card.rarity or "").lower(), 0)
    ranked = sorted(by_name.items(), key=lambda kv: (-kv[1], kv[0]))
    return [name for name, _ in ranked[:limit]]


class PoolSummary(BaseModel):
    index: int  # 0 = most recently active; also the default selection in the UI
    timestamp: str | None
    event: str | None
    set_code: str | None
    card_count: int
    sample_cards: list[str]
    grp_ids: list[int]  # echoed back to /api/sealed/build so the exact pool is what gets built


class PoolListResponse(BaseModel):
    pools: list[PoolSummary]
    detailed_logs: bool | None
    log_path: str | None


class PoolBuildRequest(BaseModel):
    grp_ids: list[int]
    set_code: str | None = None
    event: str | None = None
    guidance: str = ""  # free-text steer for the AI build ("lean aggressive", "splash red"…)
    prior: PriorBuild | None = None  # set on "Iterate with AI" to refine the last build


@app.get("/api/sealed/pools", response_model=PoolListResponse)
def sealed_pools(
    log: str | None = Query(None, description="Path to a specific Arena Player.log."),
) -> PoolListResponse:
    """List every distinct full sealed pool in the Arena log so the user can pick the right one.

    Empty (rather than an error) when no log or no pool is found — the UI shows guidance and the
    user can still build from the bundled sample.
    """
    path = Path(log).expanduser() if log else find_arena_log()
    if path is None or not path.exists():
        return PoolListResponse(pools=[], detailed_logs=None, log_path=None)
    text = path.read_text(errors="ignore")
    parsed = list_pools(text)
    repo = _card_repo()
    pools = [
        PoolSummary(
            index=i,
            timestamp=p.timestamp,
            event=p.event,
            set_code=p.set_code,
            card_count=len(p.grp_ids),
            sample_cards=_sample_card_names(repo, p.grp_ids),
            grp_ids=p.grp_ids,
        )
        for i, p in enumerate(parsed)
    ]
    return PoolListResponse(
        pools=pools, detailed_logs=detailed_logs_status(text), log_path=str(path)
    )


@app.get("/api/sealed/status")
def sealed_status() -> dict:
    """Tell the UI whether the AI build is available (an Anthropic API key is configured)."""
    return {"ai_available": ai_available()}


@app.get("/api/sealed/demo", response_model=SealedResult)
def sealed_demo(
    ai: bool = Query(False, description="Let the AI reason over the build (uses the API key)."),
    guidance: str = Query("", description="Free-text steer for the AI build."),
) -> SealedResult:
    """Build from the bundled sample pool — deterministic by default; AI when ai=true."""
    return _run_sealed(load_pool_fixture(_FIXTURE), use_ai=ai and ai_available(), guidance=guidance)


@app.get("/api/sealed/build", response_model=SealedResult)
def sealed_build(
    log: str | None = Query(None, description="Path to a specific Arena Player.log."),
    ai: bool = Query(False, description="Let the AI reason over the build (uses the API key)."),
    guidance: str = Query("", description="Free-text steer for the AI build."),
):
    """Build from the player's live Arena sealed pool (auto-found log)."""
    try:
        parsed = load_pool(log)
    except ArenaLogError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return _run_sealed(parsed, use_ai=ai and ai_available(), guidance=guidance)


@app.post("/api/sealed/build", response_model=SealedResult)
def sealed_build_selected(
    req: PoolBuildRequest,
    ai: bool = Query(False, description="Let the AI reason over the build (uses the API key)."),
) -> SealedResult:
    """Build from a specific pool the user chose in the picker (see `/api/sealed/pools`).

    The exact card ids are posted back, so this builds precisely the selected pool — no
    re-guessing which of several pools in the log to use. `guidance` (in the body) steers the AI.
    """
    if not req.grp_ids:
        raise HTTPException(status_code=400, detail="The selected pool has no cards.")
    parsed = ParsedPool(
        grp_ids=req.grp_ids, event=req.event, set_code=req.set_code, detailed_logs=True
    )
    return _run_sealed(
        parsed, use_ai=ai and ai_available(), guidance=req.guidance, prior=req.prior
    )


# Serve the built SPA when present. Mounted LAST so the /api/* routes above take precedence.
if _DIST.exists():
    app.mount("/", StaticFiles(directory=str(_DIST), html=True), name="spa")
