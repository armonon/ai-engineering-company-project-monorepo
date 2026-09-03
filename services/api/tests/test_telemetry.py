"""Temporary telemetry receiver and privacy-preserving auth identity."""

from __future__ import annotations

import logging

import pytest
from fastapi.testclient import TestClient


def event(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "eventId": "4cb11120-71a6-4a8f-a2d5-0cb59287fe14",
        "timestamp": "2026-09-02T17:14:29.000Z",
        "sessionId": "sess_demo",
        "userId": "anonymous",
        "event_type": "page_viewed",
        "schemaVersion": "1.0.0",
        "requestId": "req_demo",
        "properties": {"route_template": "/", "secret": "must-not-be-logged"},
    }
    return {**base, **overrides}


def test_stub_accepts_a_batch_and_logs_only_safe_metadata(
    api: TestClient,
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level(logging.INFO, logger="uvicorn.error.trackflow.telemetry"):
        response = api.post(
            "/telemetry/events",
            json={"events": [event(), event(event_type="api_latency_recorded")]},
        )

    assert response.status_code == 200
    assert response.json() == {"received": 2}
    assert "count=2" in caplog.text
    assert "page_viewed" in caplog.text
    assert "api_latency_recorded" in caplog.text
    assert "must-not-be-logged" not in caplog.text


@pytest.mark.parametrize(
    "change",
    [
        {"eventId": "not-a-uuid"},
        {"timestamp": "2026-09-02T17:14:29"},
        {"userId": "42"},
        {"event_type": "PageViewed"},
        {"schemaVersion": "v1"},
        {"unexpected": "field"},
    ],
)
def test_stub_rejects_malformed_standard_envelopes(
    api: TestClient,
    change: dict[str, object],
) -> None:
    response = api.post("/telemetry/events", json={"events": [event(**change)]})
    assert response.status_code == 422


def test_backend_reads_telemetry_endpoint_from_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from routers.telemetry import telemetry_endpoint

    monkeypatch.setenv("TELEMETRY_ENDPOINT", "https://events.internal.example/v1")
    assert telemetry_endpoint() == "https://events.internal.example/v1"


def test_login_and_me_return_the_same_non_identifying_user_id(
    api: TestClient,
    registered: dict,
) -> None:
    login = api.post(
        "/auth/login",
        json={"email": registered["email"], "password": registered["password"]},
    )
    assert login.status_code == 200
    body = login.json()
    assert body["telemetry_user_id"].startswith("usr_")
    assert len(body["telemetry_user_id"]) == 68
    assert body["telemetry_user_id"] != str(registered["user"]["id"])

    api.headers["Authorization"] = f"Bearer {body['access_token']}"
    me = api.get("/auth/me")
    assert me.json()["telemetry_user_id"] == body["telemetry_user_id"]
    assert body["role"] == me.json()["role"]
