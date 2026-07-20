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

from fastapi import FastAPI, File, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .core.config import Settings, get_secrets
from .draft.models import PipelineResult
from .draft.pipeline import build_pipeline

# The built frontend (web/dist), if it has been produced by `npm run build`.
_DIST = Path(__file__).resolve().parents[2] / "web" / "dist"


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


app = FastAPI(title="MTG Arena Draft Assistant", version="0.1.0", lifespan=lifespan)

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


# Serve the built SPA when present. Mounted LAST so the /api/* routes above take precedence.
if _DIST.exists():
    app.mount("/", StaticFiles(directory=str(_DIST), html=True), name="spa")
