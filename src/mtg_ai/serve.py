"""One-command app launcher: `mtg-draft-app`.

Builds the web UI if it hasn't been built yet, starts the FastAPI server (which serves both the
API and the UI on one port), and opens the browser. No two-terminal dance, no env vars.

Cost note: the app boots on the safe mock backend. Real models are only used when you flip the
"Use real models" toggle in the UI (and only if ANTHROPIC_API_KEY is set).
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import threading
import webbrowser
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_WEB = _ROOT / "web"
_DIST = _WEB / "dist"

HOST = "127.0.0.1"
PORT = 8000


def _ensure_ui_built() -> bool:
    """Build web/dist if missing. Returns True if the UI is available to serve."""
    if _DIST.exists():
        return True
    npm = shutil.which("npm")
    if npm is None:
        print(
            "The UI isn't built yet and `npm` was not found.\n"
            "Install Node (e.g. `brew install node`) and re-run, or run the dev server manually:\n"
            "    cd web && npm install && npm run dev",
            file=sys.stderr,
        )
        return False
    if not (_WEB / "node_modules").exists():
        print("Installing UI dependencies (first run only)...")
        subprocess.run([npm, "install"], cwd=_WEB, check=True)
        # Newer npm may skip esbuild's postinstall; make sure its binary is present.
        subprocess.run([npm, "rebuild", "esbuild"], cwd=_WEB, check=False)
    print("Building the web UI (first run only)...")
    subprocess.run([npm, "run", "build"], cwd=_WEB, check=True)
    return _DIST.exists()


def main() -> None:
    if not _ensure_ui_built():
        sys.exit(1)

    import uvicorn

    url = f"http://{HOST}:{PORT}"
    # Open the browser shortly after the server starts accepting connections.
    threading.Timer(1.5, lambda: webbrowser.open(url)).start()
    print(f"\n  MTG Draft Assistant is running →  {url}")
    print("  (mock backend — free; flip 'Use real models' in the UI to analyze real screenshots)")
    print("  Press Ctrl+C to stop.\n")
    uvicorn.run("mtg_ai.api:app", host=HOST, port=PORT, log_level="warning")


if __name__ == "__main__":
    main()
