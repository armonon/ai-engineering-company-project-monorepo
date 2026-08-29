"""API-level tests for the incident-analysis endpoints."""

from __future__ import annotations

import io
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from main import app


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    """An authenticated client on a throwaway TinyDB.

    The incident routes require a token since the auth milestone.
    These tests cover analysis behaviour; the 401-without-a-token
    cases live in test_auth.py.
    """
    monkeypatch.setenv("TINYDB_PATH", str(tmp_path / "incidents.json"))
    monkeypatch.setenv("SECRET_KEY", "test-secret-not-a-real-one-32-bytes-minimum")
    monkeypatch.setenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60")

    import database

    database.close_db()

    with TestClient(app) as c:
        c.post(
            "/users",
            json={"email": "analyst@trackflow.com", "password": "test-password-123"},
        )
        token = c.post(
            "/auth/login",
            json={"email": "analyst@trackflow.com", "password": "test-password-123"},
        ).json()["access_token"]
        c.headers.update({"Authorization": f"Bearer {token}"})
        yield c

    database.close_db()

_FIXTURE = (
    Path(__file__).resolve().parents[3] / "scripts" / "incidents-trackflow.csv"
)


def _upload(client_: TestClient, payload: bytes, filename: str = "incidents.csv"):
    return client_.post(
        "/api/incidents/analyze",
        files={"file": (filename, io.BytesIO(payload), "text/csv")},
    )


def test_health(client: TestClient) -> None:
    r = client.get("/")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_analyze_returns_context_expected_values(client: TestClient) -> None:
    payload = _FIXTURE.read_bytes()
    r = _upload(client, payload)
    assert r.status_code == 200
    body = r.json()
    assert body["totals"] == {
        "total_rows": 100,
        "valid_records": 95,
        "invalid_records": 5,
    }
    assert body["category_breakdown"] == {
        "LOST_PARCEL": 14,
        "DELAYED_DELIVERY": 38,
        "WRONG_ADDRESS": 19,
        "RETURN_REQUEST": 17,
        "DAMAGE": 7,
    }
    assert body["status_breakdown"] == {"OPEN": 29, "CLOSED": 52, "DISCARDED": 14}
    assert body["country_breakdown"] == {"US": 50, "ES": 45}
    assert body["satisfaction"]["average_score"] == 3.06
    assert body["satisfaction"]["closed_incidents"] == 52


def test_analyze_rejects_non_csv(client: TestClient) -> None:
    r = client.post(
        "/api/incidents/analyze",
        files={"file": ("nope.txt", io.BytesIO(b"plain text"), "text/plain")},
    )
    assert r.status_code == 400


def test_analyze_rejects_empty_body(client: TestClient) -> None:
    r = client.post(
        "/api/incidents/analyze",
        files={"file": ("empty.csv", io.BytesIO(b""), "text/csv")},
    )
    assert r.status_code == 400


def test_analyze_rejects_header_only_csv(client: TestClient) -> None:
    header_only = b"incident_id,date,country\n"
    r = _upload(client, header_only)
    assert r.status_code == 422


def test_export_before_any_analysis_returns_404(client: TestClient) -> None:
    import routers.incidents as api_main

    api_main._LAST_RESULT = None
    r = client.get("/api/incidents/results/export")
    assert r.status_code == 404


def test_export_after_analysis_returns_csv(client: TestClient) -> None:
    payload = _FIXTURE.read_bytes()
    _upload(client, payload)  # populate cache

    r = client.get("/api/incidents/results/export")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/csv")
    assert "trackflow-incidents-results.csv" in r.headers["content-disposition"]

    body = r.text
    # No emails in the exported CSV — CONTEXT rule.
    assert "@" not in body
    # Header + one row per metric.
    assert body.splitlines()[0] == "metric,category,value"
    assert "total_rows,100" in body
    assert "valid_records,95" in body
