"""Persistent telemetry storage and privacy-preserving auth identity."""

from __future__ import annotations

import logging
import shlex
from collections.abc import Iterator
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

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


def test_backend_image_packages_the_runtime_catalogue(
    api: TestClient,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Exercise ingestion using only the catalogue shipped by Docker COPY.

    This is a filesystem packaging regression, not a Docker execution test.
    It fails if the image omits the catalogue or puts it at the wrong path.
    """
    from routers import telemetry

    root = Path(__file__).resolve().parents[3]
    catalogue = root / "docs/telemetry/event-schemas.json"
    image_root = tmp_path / "image/workspace"
    for line in (root / "services/Dockerfile").read_text().splitlines():
        if not line.startswith("COPY "):
            continue
        parts = shlex.split(line)
        for source in parts[1:-1]:
            source_path = root / source
            if source_path == catalogue:
                destination = image_root / parts[-1]
                if parts[-1].endswith("/"):
                    destination /= catalogue.name
            elif catalogue.is_relative_to(source_path):
                destination = image_root / parts[-1] / catalogue.relative_to(source_path)
            else:
                continue
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(catalogue.read_bytes())

    monkeypatch.setattr(telemetry, "_CATALOGUE_PATH", image_root / catalogue.relative_to(root))
    telemetry._catalogue_events.cache_clear()
    try:
        response = api.post("/telemetry/events", json={"events": [telemetry_event()]})
        assert response.status_code == 200
        assert response.json() == {"received": 1, "stored": 1, "rejected": 0}
        assert len(stored_rows()) == 1
    finally:
        telemetry._catalogue_events.cache_clear()


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
    assert indexes["ix_telemetry_events_tags_gin"].dialect_options["postgresql"]["using"] == "gin"


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


@pytest.mark.parametrize("warehouse", ["los_angeles", "zaragoza"])
@pytest.mark.parametrize("event_type", ["inbound_order_created", "outbound_order_created"])
def test_business_events_preserve_company_dimensions(
    api: TestClient,
    warehouse: str,
    event_type: str,
) -> None:
    properties = {
        "warehouse": warehouse,
        "client_id": "client_test",
        "product_id": "CLT-SNK-W-42" if warehouse == "los_angeles" else "CLT-SNK-W-42-Z",
        "product_category": "fashion",
        "quantity": 3,
        "order_id": "order_test",
    }
    if event_type == "outbound_order_created":
        properties["exit_type"] = "dispatch"
    response = api.post(
        "/telemetry/events",
        json={"events": [telemetry_event(event_type=event_type, properties=properties)]},
    )
    assert response.json() == {"received": 1, "stored": 1, "rejected": 0}
    row = stored_rows()[0]
    assert row.event_type == event_type
    assert row.service == "backoffice"
    assert row.value == Decimal("3")
    assert {key: row.tags[key] for key in properties} == properties


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("duration_ms", -1),
        ("duration_ms", True),
        ("duration_ms", "47"),
        ("duration_ms", 1.5),
        ("slo_exceeded", 1),
        ("method", "TRACE"),
        ("endpoint_template", ""),
    ],
)
def test_invalid_property_values_do_not_discard_valid_siblings(
    api: TestClient,
    field: str,
    value: object,
) -> None:
    invalid = api_latency_event()
    invalid["properties"] = {**invalid["properties"], field: value}
    response = api.post(
        "/telemetry/events",
        json={"events": [telemetry_event(), invalid]},
    )
    assert response.json() == {"received": 2, "stored": 1, "rejected": 1}
    assert [row.event_type for row in stored_rows()] == ["page_viewed"]


@pytest.mark.parametrize("status_code", [399, 600])
def test_error_status_range_is_enforced(api: TestClient, status_code: int) -> None:
    properties = {
        "service": "trackflow_api",
        "endpoint_template": "/inventory/products",
        "method": "GET",
        "status_code": status_code,
        "error_code": "REQUEST_FAILED",
        "duration_ms": 0,
        "retryable": False,
    }
    response = api.post(
        "/telemetry/events",
        json={"events": [telemetry_event(event_type="api_error_returned", properties=properties)]},
    )
    assert response.json() == {"received": 1, "stored": 0, "rejected": 1}
    assert stored_rows() == []


def test_pattern_uuid_and_version_failures_are_rejected_per_event(api: TestClient) -> None:
    invalid_hash = telemetry_event(
        event_type="login_failed",
        properties={
            "auth_method": "password",
            "reason_code": "invalid_credentials",
            "attempt_number": 1,
            "principal_hash": "not-a-pseudonym",
        },
    )
    invalid_uuid = telemetry_event(
        event_type="workflow_started",
        properties={
            "workflow_name": "inventory_inbound",
            "flow_instance_id": "not-a-uuid",
            "entry_point": "navigation",
        },
    )
    response = api.post(
        "/telemetry/events",
        json={
            "events": [
                invalid_hash,
                invalid_uuid,
                telemetry_event(schemaVersion="2.0.0"),
                telemetry_event(),
            ]
        },
    )
    assert response.json() == {"received": 4, "stored": 1, "rejected": 3}
    assert len(stored_rows()) == 1


def test_empty_batch_does_not_create_rows(api: TestClient) -> None:
    response = api.post("/telemetry/events", json={"events": []})
    assert response.status_code == 200
    assert response.json() == {"received": 0, "stored": 0, "rejected": 0}
    assert stored_rows() == []


def test_failed_bulk_insert_rolls_back_every_row_and_session_recovers(
    api: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A real database constraint failure must not leave an accepted prefix."""
    import database
    from routers import telemetry
    from schemas import TelemetryEvent

    duplicate_id = uuid4()
    monkeypatch.setattr(telemetry, "uuid4", lambda: duplicate_id)
    events = [
        TelemetryEvent.model_validate(telemetry_event()),
        TelemetryEvent.model_validate(api_latency_event()),
    ]

    from sqlalchemy.exc import IntegrityError

    with Session(database.inventory_engine()) as session:
        with pytest.raises(IntegrityError):
            telemetry.persist_telemetry_events(session, events, received=2, rejected=0)
        assert list(session.exec(select(TelemetryEventRecord)).all()) == []
        receipt = telemetry.persist_telemetry_events(session, events[:1], received=1, rejected=0)
        assert receipt.stored == 1
    assert len(stored_rows()) == 1


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
