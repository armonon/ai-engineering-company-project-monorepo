"""Acceptance coverage for the Part 2 resilient business pipeline."""

from __future__ import annotations

import importlib
import time
from collections.abc import Iterator
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from prefect.testing.utilities import prefect_test_harness
from sqlalchemy import JSON, Column, DateTime, MetaData, String, Table, Uuid, create_engine, func
from sqlalchemy.sql import select
from trackflow_pipeline.pipeline import (
    load_weekly_performance,
    record_pipeline_run_start,
    weekly_warehouse_client_performance_flow,
)
from trackflow_pipeline.queries import get_latest_run
from trackflow_pipeline.storage import ensure_reporting_schema
from trackflow_process import PipelineQualityError, transform_weekly_performance


def _event(
    event_type: str,
    *,
    event_id: str | None = None,
    quantity: int = 1,
    timestamp: datetime | None = None,
) -> dict:
    return {
        "id": str(uuid4()),
        "timestamp": timestamp or datetime(2026, 7, 15, 12, tzinfo=UTC),
        "event_type": event_type,
        "tags": {
            "event_id": event_id or str(uuid4()),
            "warehouse": "los_angeles",
            "client_id": "client_01JTF000000000000000000001",
            "product_id": "CLT-SNK-W-42",
            "product_category": "fashion",
            "quantity": quantity,
        },
    }


def _source_table(database_url: str) -> Table:
    engine = create_engine(database_url)
    metadata = MetaData()
    source = Table(
        "telemetry_events",
        metadata,
        Column("id", Uuid(as_uuid=False), primary_key=True),
        Column("timestamp", DateTime(timezone=True), nullable=False),
        Column("event_type", String, nullable=False),
        Column("tags", JSON, nullable=False),
    )
    metadata.create_all(engine)
    engine.dispose()
    return source


def test_transform_uses_exact_trackflow_kpis_and_deduplicates() -> None:
    duplicate_id = str(uuid4())
    inbound = _event("inbound_order_created", event_id=duplicate_id, quantity=12)
    result = transform_weekly_performance(
        [
            inbound,
            {**inbound, "id": str(uuid4())},
            _event("outbound_order_created", quantity=8),
            _event("outbound_order_created", quantity=2),
            _event("stock_threshold_triggered", quantity=0),
            _event("inventory_discrepancy_detected", quantity=3),
        ]
    )

    assert result["records_processed"] == 6
    assert result["deduplicated"] == 1
    assert result["rows"] == [
        {
            "warehouse": "los_angeles",
            "client_id": "client_01JTF000000000000000000001",
            "week_start": date(2026, 7, 13),
            "inbound_units_count": 12,
            "outbound_orders_count": 2,
            "stockout_events_count": 1,
            "discrepancy_events_count": 1,
            "discrepancy_rate": pytest.approx(0.5),
        }
    ]


def test_transform_rejects_conflicting_duplicate_event_ids() -> None:
    event_id = str(uuid4())
    first = _event("inbound_order_created", event_id=event_id, quantity=12)
    conflicting = _event("inbound_order_created", event_id=event_id, quantity=13)
    with pytest.raises(PipelineQualityError, match="conflicting"):
        transform_weekly_performance([first, conflicting])


def test_idempotent_load_keeps_one_absolute_business_row(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database_url = f"sqlite:///{tmp_path / 'pipeline.db'}"
    monkeypatch.setenv("PIPELINE_DATABASE_URL", database_url)
    start = datetime(2026, 7, 13, tzinfo=UTC)
    end = start + timedelta(days=7)
    transformed = transform_weekly_performance([_event("inbound_order_created", quantity=12)])

    for _ in range(2):
        run_id = str(uuid4())
        record_pipeline_run_start.fn(run_id, start, end, "manual")
        assert load_weekly_performance.fn(run_id, start, end, transformed) == 1

    engine = create_engine(database_url)
    weekly, runs = ensure_reporting_schema(engine)
    with engine.connect() as connection:
        assert connection.scalar(select(func.count()).select_from(weekly)) == 1
        row = connection.execute(select(weekly)).mappings().one()
        assert row.inbound_units_count == 12
        assert connection.scalar(select(func.count()).select_from(runs)) == 2
    engine.dispose()


def test_optional_snapshot_failure_does_not_fail_the_flow(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database_url = f"sqlite:///{tmp_path / 'flow.db'}"
    monkeypatch.setenv("PIPELINE_DATABASE_URL", database_url)
    source = _source_table(database_url)
    engine = create_engine(database_url)
    event = _event("inbound_order_created", quantity=7)
    with engine.begin() as connection:
        connection.execute(source.insert().values(**event))
    engine.dispose()

    not_a_directory = tmp_path / "not-a-directory"
    not_a_directory.write_text("blocks mkdir", encoding="utf-8")
    monkeypatch.setenv("PIPELINE_EVAL_DIRECTORY", str(not_a_directory))

    with prefect_test_harness():
        result = weekly_warehouse_client_performance_flow(
            window_start=datetime(2026, 7, 13, tzinfo=UTC),
            window_end=datetime(2026, 7, 20, tzinfo=UTC),
            trigger="manual",
        )
    assert result["status"] == "Completed"
    assert result["rows_committed"] == 1
    assert result["optional_snapshot_status"] == "Failed"
    assert get_latest_run()["status"] == "Completed"


@pytest.fixture
def reporting_api(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    monkeypatch.setenv("TINYDB_PATH", str(tmp_path / "users.json"))
    monkeypatch.setenv("SECRET_KEY", "test-secret-not-a-real-one-32-bytes-minimum")
    monkeypatch.setenv("TELEMETRY_HMAC_KEY", "telemetry-test-key-that-is-at-least-32-bytes")
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'api.db'}")
    monkeypatch.delenv("PIPELINE_DATABASE_URL", raising=False)

    import database

    database.close_db()
    database.dispose_inventory_engine()
    from main import app

    with TestClient(app) as client:
        response = client.post(
            "/users",
            json={"email": "manager@trackflow.com", "password": "correct-password"},
        )
        user = response.json()
        from database import users_table

        users_table().update({"role": "manager"}, doc_ids=[user["id"]])
        token = client.post(
            "/auth/login",
            json={"email": "manager@trackflow.com", "password": "correct-password"},
        ).json()["access_token"]
        client.headers["Authorization"] = f"Bearer {token}"
        yield client

    database.dispose_inventory_engine()
    database.close_db()


def test_reporting_endpoints_follow_the_briefing_contract(
    reporting_api: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    reporting_router = importlib.import_module("reporting.router")
    submitted: list[dict] = []
    monkeypatch.setattr(
        reporting_router,
        "enqueue_weekly_performance_task",
        lambda **kwargs: submitted.append(kwargs) or "celery-task-123",
    )

    latest = reporting_api.get("/reporting/pipeline-runs/latest")
    assert latest.status_code == 200
    assert latest.json() == {"run": None}

    report = reporting_api.get("/reporting/weekly-warehouse-client-performance")
    assert report.status_code == 200
    assert report.json() == {"week_start": None, "entries": []}

    started = time.perf_counter()
    trigger = reporting_api.post("/reporting/pipeline-runs", json={"week_start": "2026-07-13"})
    elapsed = time.perf_counter() - started
    assert trigger.status_code == 202
    assert elapsed < 0.2
    assert trigger.json()["status"] == "Accepted"
    assert trigger.json()["task_id"] == "celery-task-123"
    assert trigger.json()["status_url"] == "/tasks/celery-task-123"
    assert len(submitted) == 1

    bad_week = reporting_api.get(
        "/reporting/weekly-warehouse-client-performance?week_start=2026-07-14"
    )
    assert bad_week.status_code == 422
