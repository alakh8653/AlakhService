"""Smoke test: the FastAPI app must import and serve its health endpoint."""
from fastapi.testclient import TestClient

from app.main import app


def test_app_starts_and_reports_healthy():
    with TestClient(app) as client:
        resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "healthy"
