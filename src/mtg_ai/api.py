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

from .core.config import Settings, get_secrets
from .draft.models import PipelineResult
from .draft.pipeline import build_pipeline
from .sealed.ingest_log import ArenaLogError, ParsedPool, load_pool, load_pool_fixture
from .sealed.models import SealedResult
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


def _run_sealed(parsed: ParsedPool, use_ai: bool = False) -> SealedResult:
    settings = Settings()
    if parsed.set_code:
        settings.default_set = parsed.set_code
    ratings = load_ratings(settings)  # cached; network only on first fetch
    return build_sealed_pipeline(settings, ratings=ratings, use_llm=use_ai).run(parsed)


@app.get("/api/sealed/status")
def sealed_status() -> dict:
    """Tell the UI whether the AI build is available (an Anthropic API key is configured)."""
    return {"ai_available": ai_available()}


@app.get("/api/sealed/demo", response_model=SealedResult)
def sealed_demo(
    ai: bool = Query(False, description="Let the AI reason over the build (uses the API key)."),
) -> SealedResult:
    """Build from the bundled sample pool — deterministic by default; AI when ai=true."""
    return _run_sealed(load_pool_fixture(_FIXTURE), use_ai=ai and ai_available())


@app.get("/api/sealed/build", response_model=SealedResult)
def sealed_build(
    log: str | None = Query(None, description="Path to a specific Arena Player.log."),
    ai: bool = Query(False, description="Let the AI reason over the build (uses the API key)."),
):
    """Build from the player's live Arena sealed pool (auto-found log)."""
    try:
        parsed = load_pool(log)
    except ArenaLogError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return _run_sealed(parsed, use_ai=ai and ai_available())


# Serve the built SPA when present. Mounted LAST so the /api/* routes above take precedence.
if _DIST.exists():
    app.mount("/", StaticFiles(directory=str(_DIST), html=True), name="spa")
