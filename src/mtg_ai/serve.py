"""One-command app launcher: `mtg-ai`.

Builds the web UI if it hasn't been built yet, starts the FastAPI server (which serves both the
API and the UI on one port), and opens the browser. No two-terminal dance, no env vars.

Robust restart: closing the Terminal can orphan the old server (it keeps holding the port), which
used to make the next launch fail with "address already in use". On startup we detect a leftover
*our-app* server and stop it so the port is reusable; if something unrelated holds the port, we
quietly move to the next free one instead of erroring.

Cost note: the app boots free/deterministic. Real models are only used when you press "Build with
AI" (and only if ANTHROPIC_API_KEY is set).
"""

from __future__ import annotations

import json
import os
import shutil
import signal
import socket
import subprocess
import sys
import threading
import time
import urllib.request
import webbrowser
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_WEB = _ROOT / "web"
_DIST = _WEB / "dist"

HOST = "127.0.0.1"
PORT = 8000
_PORT_RANGE = 10  # if 8000 is taken by something else, try 8001..8010


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


def _port_open(port: int) -> bool:
    """True if something is already accepting connections on HOST:port."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.3)
        return s.connect_ex((HOST, port)) == 0


def _is_our_server(port: int) -> bool:
    """True if the server on `port` is a mtg_ai instance (has our sealed API), not some other app."""
    try:
        with urllib.request.urlopen(f"http://{HOST}:{port}/api/sealed/status", timeout=0.6) as r:
            return r.status == 200 and "ai_available" in json.loads(r.read().decode() or "{}")
    except Exception:  # noqa: BLE001 - any failure just means "not our server / not reachable"
        return False


def _pids_on_port(port: int) -> list[int]:
    """PIDs listening on `port` (via lsof; empty if lsof is unavailable)."""
    lsof = shutil.which("lsof")
    if not lsof:
        return []
    out = subprocess.run(
        [lsof, "-ti", f"tcp:{port}", "-sTCP:LISTEN"], capture_output=True, text=True
    )
    return [int(x) for x in out.stdout.split() if x.strip().isdigit()]


def _reclaim_port(port: int) -> bool:
    """Stop whatever mtg_ai process is holding `port`. Returns True once the port is free."""
    def _still_held() -> bool:
        return _port_open(port)

    for sig in (signal.SIGTERM, signal.SIGKILL):
        pids = _pids_on_port(port)
        if not pids:
            break
        for pid in pids:
            try:
                os.kill(pid, sig)
            except ProcessLookupError:
                pass
        # Give it up to ~2s to release the socket before escalating to SIGKILL.
        for _ in range(20):
            if not _still_held():
                return True
            time.sleep(0.1)
    return not _still_held()


def _choose_port() -> int | None:
    """Decide which port to serve on, self-healing a stale prior instance.

    Free -> use 8000. Held by a leftover mtg_ai server (Terminal closed but it kept running) ->
    stop it and reuse 8000, so restarts always work. Held by something else -> use the next free
    port and leave that other process alone. None if nothing in the range is free.
    """
    if not _port_open(PORT):
        return PORT
    if _is_our_server(PORT):
        print("  A previous MTG AI server is still running — stopping it and restarting cleanly…")
        if _reclaim_port(PORT):
            return PORT
        print("  Couldn't free port 8000; falling back to another port.")
    else:
        print(f"  Port {PORT} is used by another program — serving on a nearby port instead.")
    for port in range(PORT + 1, PORT + 1 + _PORT_RANGE):
        if not _port_open(port):
            return port
    return None


def main() -> None:
    if not _ensure_ui_built():
        sys.exit(1)

    import uvicorn

    port = _choose_port()
    if port is None:
        print(
            f"No free port found in {PORT}-{PORT + _PORT_RANGE}. "
            "Close some servers (or run: lsof -ti:8000 | xargs kill) and try again.",
            file=sys.stderr,
        )
        sys.exit(1)

    url = f"http://{HOST}:{port}"
    # Open the browser shortly after the server starts accepting connections.
    threading.Timer(1.5, lambda: webbrowser.open(url)).start()
    print(f"\n  MTG AI — Sealed Deck Builder is running →  {url}")
    print("  Pick your pool up top, then Quick build, or ✦ Build with AI with an optional steer.")
    print("  (Quick build is free — no API key needed.)  Press Ctrl+C to stop.\n")
    uvicorn.run("mtg_ai.api:app", host=HOST, port=port, log_level="warning")


if __name__ == "__main__":
    main()
