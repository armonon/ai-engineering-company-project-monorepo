"""Real SQL/Pandas metrics, boundaries, authentication and deterministic cache tests."""

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select
from telemetry import analysis

from database import get_db
from main import app
from models import TelemetryEventRecord
from routers import telemetry_report as reporting
from security import get_current_user

START = datetime(2026, 10, 1, tzinfo=UTC)
END = START + timedelta(days=2)
PARAMS = {"start_date": START.isoformat(), "end_date": END.isoformat()}


@pytest.fixture
def report_api() -> Iterator[tuple]:
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    SQLModel.metadata.create_all(engine)

    def session() -> Iterator[Session]:
        with Session(engine) as db:
            yield db

    previous = dict(app.dependency_overrides)
    app.dependency_overrides[get_db] = session
    app.dependency_overrides[get_current_user] = lambda: {"id": 1}
    reporting.clear_report_cache()
    try:
        yield TestClient(app), engine
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous)
        reporting.clear_report_cache()
        engine.dispose()


def add(engine, kind="page_viewed", at=START, level="info", value=None, tags=None):
    with Session(engine) as session:
        session.add(
            TelemetryEventRecord(
                id=uuid4(),
                timestamp=at,
                service="api",
                event_type=kind,
                level=level,
                value=value,
                tags=tags or {},
            )
        )
        session.commit()


def test_metrics_have_exact_utc_groups_denominators_and_dimensions(report_api):
    client, engine = report_api
    add(engine, "login_failed")
    add(engine, "login_succeeded")
    add(engine, "login_succeeded")
    add(engine, "api_error_returned", level="error")
    add(engine, "api_latency_recorded", value=100, tags={"endpoint_template": "/a"})
    add(engine, "api_latency_recorded", value=300, tags={"endpoint_template": "/a"})
    add(engine, "api_latency_recorded", value=900, tags={"endpoint_template": "/b"})
    add(engine, "page_viewed", at=START + timedelta(days=1))
    # Inclusive start/exclusive end must be enforced by SQL, not DataFrame filtering.
    add(engine, "login_failed", at=START - timedelta(microseconds=1))
    add(engine, "login_failed", at=END)
    add(engine, "unknown_event")
    result = client.get("/telemetry/report", params=PARAMS)
    assert result.status_code == 200
    metrics = result.json()["metrics"]
    assert metrics["auth_failure_rate"] == [
        {"date": "2026-10-01", "attempts": 3, "failures": 1, "failure_rate": 1 / 3}
    ]
    assert metrics["latency_by_endpoint"] == [
        {"date": "2026-10-01", "endpoint_template": "/a", "samples": 2, "mean_duration_ms": 200},
        {"date": "2026-10-01", "endpoint_template": "/b", "samples": 1, "mean_duration_ms": 900},
    ]
    assert metrics["error_rate_by_day"] == [
        {
            "date": "2026-10-01",
            "service": "api",
            "total_events": 7,
            "error_events": 1,
            "error_rate": 1 / 7,
        },
        {
            "date": "2026-10-02",
            "service": "api",
            "total_events": 1,
            "error_events": 0,
            "error_rate": 0,
        },
    ]
    assert sum(row["count"] for row in metrics["events_per_day"]) == 8
    assert not any(row["event_type"] == "unknown_event" for row in metrics["events_per_day"])


def test_all_metric_queries_filter_timestamp_and_types_in_sql(report_api):
    client, engine = report_api
    captured = []

    def capture(_conn, _cursor, statement, parameters, _context, _many):
        if "SELECT" in statement and "telemetry_events" in statement:
            captured.append((statement, parameters))

    event.listen(engine, "before_cursor_execute", capture)
    try:
        assert client.get("/telemetry/report", params=PARAMS).status_code == 200
    finally:
        event.remove(engine, "before_cursor_execute", capture)
    assert len(captured) == 4
    for statement, parameters in captured:
        assert "WHERE" in statement
        assert "timestamp >=" in statement and "timestamp <" in statement
        assert "event_type IN" in statement
        assert "2026-10-01" not in statement  # bound, not interpolated
        assert parameters[0].startswith("2026-10-01")
        assert parameters[1].startswith("2026-10-03")
    assert set(captured[-1][1][2:]) == {"login_failed", "login_succeeded"}


def test_empty_database_returns_four_empty_serializable_metrics(report_api):
    client, _ = report_api
    response = client.get("/telemetry/report", params=PARAMS)
    assert response.status_code == 200
    assert response.json() == {
        "period": {"from": START.isoformat(), "to": END.isoformat()},
        "metrics": {
            "events_per_day": [],
            "error_rate_by_day": [],
            "latency_by_endpoint": [],
            "auth_failure_rate": [],
        },
    }


def test_missing_latency_dimensions_and_invalid_values_are_not_averaged(report_api):
    client, engine = report_api
    for value, tags in [
        (10, {}),
        (None, {"endpoint_template": "/a"}),
        (-1, {"endpoint_template": "/a"}),
        (float("inf"), {"endpoint_template": "/a"}),
        (20, {"endpoint_template": "/a"}),
    ]:
        add(engine, "api_latency_recorded", value=value, tags=tags)
    rows = client.get("/telemetry/report", params=PARAMS).json()["metrics"]["latency_by_endpoint"]
    assert rows == [
        {"date": "2026-10-01", "endpoint_template": "/a", "samples": 1, "mean_duration_ms": 20}
    ]


def test_explicit_window_cache_hits_expires_and_does_not_mutate_data(report_api, monkeypatch):
    client, engine = report_api
    clock = [0.0]
    monkeypatch.setattr(reporting, "time", SimpleNamespace(monotonic=lambda: clock[0]))
    first = client.get("/telemetry/report", params=PARAMS).json()
    add(engine)
    clock[0] = 59.9
    assert client.get("/telemetry/report", params=PARAMS).json() == first
    clock[0] = 60.0
    second = client.get("/telemetry/report", params=PARAMS).json()
    assert second["metrics"]["events_per_day"][0]["count"] == 1
    with Session(engine) as session:
        assert len(session.exec(select(TelemetryEventRecord)).all()) == 1


def test_default_window_is_resolved_once_and_reused_until_ttl(report_api, monkeypatch):
    client, _ = report_api
    clock = [0.0]
    now = [END]
    monkeypatch.setattr(reporting, "time", SimpleNamespace(monotonic=lambda: clock[0]))
    monkeypatch.setattr(reporting, "_utc_now", lambda: now[0])
    first = client.get("/telemetry/report").json()
    assert first["period"] == {"from": (END - timedelta(days=7)).isoformat(), "to": END.isoformat()}
    now[0] += timedelta(seconds=30)
    clock[0] = 30
    assert client.get("/telemetry/report").json() == first
    clock[0] = 60
    assert client.get("/telemetry/report").json()["period"]["to"] == now[0].isoformat()


def test_equivalent_offsets_share_cache_and_different_windows_do_not(report_api):
    client, engine = report_api
    first = client.get("/telemetry/report", params=PARAMS).json()
    add(engine)
    equivalent = {
        "start_date": "2026-09-30T17:00:00-07:00",
        "end_date": "2026-10-02T17:00:00-07:00",
    }
    assert client.get("/telemetry/report", params=equivalent).json() == first
    changed = {**PARAMS, "end_date": (END + timedelta(days=1)).isoformat()}
    assert client.get("/telemetry/report", params=changed).json()["metrics"]["events_per_day"]


@pytest.mark.parametrize(
    "params",
    [
        {"start_date": "not-a-date"},
        {"end_date": "invalid"},
        {"start_date": "2026-10-04", "end_date": "2026-10-03"},
        {"start_date": "2026-10-03", "end_date": "2026-10-03"},
        {"start_date": "2026-02-30"},
        {"end_date": "1234567890"},
        {"start_date": "0001-01-01T00:00:00+01:00"},
        {"end_date": "9999-12-31T23:59:59-01:00"},
        {"end_date": "0001-01-01T00:00:00Z"},
    ],
)
def test_invalid_dates_return_422(report_api, params):
    client, _ = report_api
    assert client.get("/telemetry/report", params=params).status_code == 422


def test_authentication_is_required_even_for_a_cached_report(report_api):
    client, _ = report_api
    assert client.get("/telemetry/report", params=PARAMS).status_code == 200
    app.dependency_overrides.pop(get_current_user)
    assert client.get("/telemetry/report", params=PARAMS).status_code == 401


def test_cache_is_bounded(report_api):
    client, _ = report_api
    for i in range(reporting.MAX_CACHE_ENTRIES + 4):
        params = {
            "start_date": START.isoformat(),
            "end_date": (END + timedelta(days=i)).isoformat(),
        }
        assert client.get("/telemetry/report", params=params).status_code == 200
    assert len(reporting._cache) == reporting.MAX_CACHE_ENTRIES


def test_functions_are_repeatable_without_writing_rows(report_api):
    _, engine = report_api
    add(engine, "login_failed")
    with engine.connect() as connection:
        first = analysis.auth_failure_rate(connection, START, END)
        assert analysis.auth_failure_rate(connection, START, END) == first
        assert first[0]["attempts"] == 1
