"""Persistent telemetry storage and privacy-preserving auth identity."""

from __future__ import annotations

import logging
from collections.abc import Iterator
from decimal import Decimal
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event as sqlalchemy_event
from sqlmodel import Session, select

from models import TelemetryEventRecord


@pytest.fixture
def api(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    """API with both stores isolated and telemetry backed by SQLite."""
    monkeypatch.setenv("TINYDB_PATH", str(tmp_path / "auth.json"))
    monkeypatch.setenv("SECRET_KEY", "test-secret-not-a-real-one-32-bytes-minimum")
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'operations.db'}")

    import database

    database.close_db()
    database.dispose_inventory_engine()

    from main import app

    with TestClient(app) as client:
        yield client

    database.close_db()
    database.dispose_inventory_engine()


def telemetry_event(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "eventId": "4cb11120-71a6-4a8f-a2d5-0cb59287fe14",
        "timestamp": "2026-09-02T17:14:29.000Z",
        "sessionId": "sess_demo",
        "userId": "anonymous",
        "event_type": "page_viewed",
        "schemaVersion": "1.0.0",
        "requestId": "req_demo",
        "properties": {
            "route_template": "/login",
            "section": "authentication",
            "previous_section": "direct",
            "viewport_class": "desktop",
        },
    }
    return {**base, **overrides}


def api_latency_event(**overrides: object) -> dict[str, object]:
    return telemetry_event(
        eventId="25947534-e118-4d2c-9a99-e8f4a01269c3",
        event_type="api_latency_recorded",
        requestId="req_api_latency",
        properties={
            "service": "trackflow_api",
            "endpoint_template": "/inventory/products",
            "method": "GET",
            "status_class": "2xx",
            "duration_ms": 47,
            "slo_exceeded": False,
        },
        **overrides,
    )


def stored_rows() -> list[TelemetryEventRecord]:
    import database

    with Session(database.inventory_engine()) as session:
        return list(
            session.exec(
                select(TelemetryEventRecord).order_by(TelemetryEventRecord.timestamp)
            ).all()
        )


def test_endpoint_persists_a_batch_and_logs_only_safe_metadata(
    api: TestClient,
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level(logging.INFO, logger="uvicorn.error.trackflow.telemetry"):
        response = api.post(
            "/telemetry/events",
            json={"events": [telemetry_event(), api_latency_event()]},
        )

    assert response.status_code == 200
    assert response.json() == {"received": 2, "stored": 2, "rejected": 0}
    assert [row.event_type for row in stored_rows()] == [
        "page_viewed",
        "api_latency_recorded",
    ]
    assert "received=2 stored=2 rejected=0" in caplog.text
    assert "page_viewed" in caplog.text
    assert "route_template" not in caplog.text


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
def test_invalid_events_are_rejected_individually_not_as_422(
    api: TestClient,
    change: dict[str, object],
) -> None:
    response = api.post(
        "/telemetry/events",
        json={"events": [telemetry_event(**change)]},
    )

    assert response.status_code == 200
    assert response.json() == {"received": 1, "stored": 0, "rejected": 1}
    assert stored_rows() == []


def test_mixed_batch_keeps_valid_events_and_rejects_only_the_bad_item(
    api: TestClient,
) -> None:
    response = api.post(
        "/telemetry/events",
        json={
            "events": [
                telemetry_event(),
                telemetry_event(eventId="invalid"),
                api_latency_event(),
            ]
        },
    )

    assert response.status_code == 200
    assert response.json() == {"received": 3, "stored": 2, "rejected": 1}
    assert len(stored_rows()) == 2


def test_non_object_items_are_rejected_without_losing_valid_siblings(
    api: TestClient,
) -> None:
    response = api.post(
        "/telemetry/events",
        json={"events": [telemetry_event(), "not-an-event", 42, None]},
    )

    assert response.status_code == 200
    assert response.json() == {"received": 4, "stored": 1, "rejected": 3}


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"events": "not-an-array"},
        {"events": [], "extra": True},
    ],
)
def test_only_a_malformed_batch_envelope_returns_422(
    api: TestClient,
    body: dict[str, object],
) -> None:
    assert api.post("/telemetry/events", json=body).status_code == 422


def test_catalogue_allowlist_and_required_properties_are_enforced(
    api: TestClient,
    caplog: pytest.LogCaptureFixture,
) -> None:
    properties = dict(telemetry_event()["properties"])
    properties["password"] = "must-never-be-stored-or-logged"

    with caplog.at_level(logging.INFO, logger="uvicorn.error.trackflow.telemetry"):
        response = api.post(
            "/telemetry/events",
            json={
                "events": [
                    telemetry_event(properties=properties),
                    telemetry_event(properties={"section": "authentication"}),
                    telemetry_event(event_type="unknown_event"),
                ]
            },
        )

    assert response.json() == {"received": 3, "stored": 0, "rejected": 3}
    assert "must-never-be-stored-or-logged" not in caplog.text
    assert stored_rows() == []


def test_storage_mapping_preserves_allowlisted_tags_and_correlation(
    api: TestClient,
) -> None:
    response = api.post("/telemetry/events", json={"events": [api_latency_event()]})
    assert response.status_code == 200

    row = stored_rows()[0]
    assert row.service == "api"
    assert row.level == "info"
    assert row.value == Decimal("47")
    assert row.message is None
    assert row.tags == {
        "service": "trackflow_api",
        "endpoint_template": "/inventory/products",
        "method": "GET",
        "status_class": "2xx",
        "duration_ms": 47,
        "slo_exceeded": False,
        "event_id": "25947534-e118-4d2c-9a99-e8f4a01269c3",
        "session_id": "sess_demo",
        "user_id": "anonymous",
        "schema_version": "1.0.0",
        "request_id": "req_api_latency",
    }


def test_valid_rows_use_one_bulk_insert_operation(api: TestClient) -> None:
    import database

    statements: list[tuple[str, bool]] = []
    engine = database.inventory_engine()

    def record(conn, cursor, statement, parameters, context, executemany):
        if "INSERT INTO telemetry_events" in statement:
            statements.append((statement, executemany))

    sqlalchemy_event.listen(engine, "before_cursor_execute", record)
    try:
        response = api.post(
            "/telemetry/events",
            json={
                "events": [
                    telemetry_event(),
                    telemetry_event(
                        eventId="f9eb8c19-55f5-4036-b2f2-56e5767dd42f",
                        requestId="req_second",
                    ),
                    api_latency_event(),
                ]
            },
        )
    finally:
        sqlalchemy_event.remove(engine, "before_cursor_execute", record)

    assert response.json() == {"received": 3, "stored": 3, "rejected": 0}
    assert len(statements) == 1
    assert statements[0][1] is True


def test_table_has_the_required_columns_and_indexes(api: TestClient) -> None:
    table = TelemetryEventRecord.__table__

    assert list(table.columns) and set(table.columns.keys()) == {
        "id",
        "timestamp",
        "service",
        "event_type",
        "level",
        "value",
        "message",
        "tags",
    }
    indexes = {index.name: index for index in table.indexes}
    assert set(indexes) == {
        "ix_telemetry_events_timestamp",
        "ix_telemetry_events_event_type",
        "ix_telemetry_events_tags_gin",
    }
    assert indexes["ix_telemetry_events_tags_gin"].dialect_options["postgresql"][
        "using"
    ] == "gin"


def test_phase_two_telemetry_event_model_is_reused_unchanged() -> None:
    from schemas import TelemetryEvent

    assert list(TelemetryEvent.model_fields) == [
        "eventId",
        "timestamp",
        "sessionId",
        "userId",
        "event_type",
        "schemaVersion",
        "requestId",
        "properties",
    ]
    assert TelemetryEvent.model_config["extra"] == "forbid"


def test_backend_reads_telemetry_endpoint_from_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from routers.telemetry import telemetry_endpoint

    monkeypatch.setenv("TELEMETRY_ENDPOINT", "https://events.internal.example/v1")
    assert telemetry_endpoint() == "https://events.internal.example/v1"


def test_login_and_me_return_the_same_non_identifying_user_id(
    api: TestClient,
) -> None:
    registered = {
        "email": "telemetry-operator@trackflow.com",
        "password": "correct-horse-battery-staple",
    }
    created = api.post("/users", json=registered)
    assert created.status_code == 201

    login = api.post("/auth/login", json=registered)
    assert login.status_code == 200
    body = login.json()
    assert body["telemetry_user_id"].startswith("usr_")
    assert len(body["telemetry_user_id"]) == 68
    assert body["telemetry_user_id"] != str(created.json()["id"])

    api.headers["Authorization"] = f"Bearer {body['access_token']}"
    me = api.get("/auth/me")
    assert me.json()["telemetry_user_id"] == body["telemetry_user_id"]
    assert body["role"] == me.json()["role"]
