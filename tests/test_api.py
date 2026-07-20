"""Stage 2 backend tests: the FastAPI endpoints run the pipeline on the mock backend."""

from __future__ import annotations

from fastapi.testclient import TestClient

from mtg_ai.api import app


def test_health():
    with TestClient(app) as client:
        assert client.get("/api/health").json() == {"status": "ok"}


def test_demo_endpoint_returns_full_result():
    with TestClient(app) as client:
        resp = client.get("/api/demo")
        assert resp.status_code == 200
        body = resp.json()
        # Full result shape is present for the UI's "why" panel.
        assert body["recommendation"]["pick"] == "Murder"
        assert body["archetype"]["committed_colors"]
        assert body["cost_log"]


def test_status_reports_live_availability():
    with TestClient(app) as client:
        body = client.get("/api/status").json()
        assert isinstance(body["live_available"], bool)


def test_demo_is_always_mock():
    # Cost safety: the demo must never touch real models, regardless of key configuration.
    with TestClient(app) as client:
        body = client.get("/api/demo").json()
        assert all(c["model"].startswith("mock:") for c in body["cost_log"])


def test_recommend_accepts_upload():
    with TestClient(app) as client:
        resp = client.post(
            "/api/recommend",
            files={"screenshot": ("draft.png", b"fake-image-bytes", "image/png")},
        )
        assert resp.status_code == 200
        # Mock backend ignores the image, but the upload path is exercised end to end.
        assert resp.json()["recommendation"]["pick"]


def test_recommend_defaults_to_mock():
    # Without ?live=true an upload stays on the free mock backend (no accidental spend).
    with TestClient(app) as client:
        body = client.post(
            "/api/recommend",
            files={"screenshot": ("draft.png", b"fake-image-bytes", "image/png")},
        ).json()
        assert all(c["model"].startswith("mock:") for c in body["cost_log"])
