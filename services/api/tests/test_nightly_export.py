"""Acceptance coverage for DEV-53 independent nightly background processing."""

from __future__ import annotations

import csv
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import insert, select

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
for import_root in (REPOSITORY_ROOT, REPOSITORY_ROOT / "services"):
    if str(import_root) not in sys.path:
        sys.path.insert(0, str(import_root))

from job_runner import (  # noqa: E402
    claim_job,
    ensure_job_schema,
    get_job_run,
    has_completed_for_date,
    has_processing_lock,
    job_runs,
    make_engine,
    update_job_run,
)
from scripts.nightly_export import (  # noqa: E402
    export_telemetry_csv,
    resolve_target_date,
    run_nightly_export,
    telemetry_table,
)


@pytest.fixture
def job_engine(tmp_path: Path):
    engine = make_engine(f"sqlite:///{tmp_path / 'jobs.db'}")
    ensure_job_schema(engine)
    source = telemetry_table()
    source.metadata.create_all(engine)
    yield engine
    engine.dispose()


def _insert_event(engine, timestamp: datetime) -> None:
    source = telemetry_table()
    with engine.begin() as connection:
        connection.execute(
            insert(source).values(
                id=str(uuid4()),
                timestamp=timestamp,
                service="backoffice",
                event_type="page_viewed",
                level="info",
                value=None,
                message=None,
                tags={"route": "/reporting"},
            )
        )


def test_target_date_defaults_to_previous_utc_day() -> None:
    assert resolve_target_date(now=datetime(2026, 10, 28, 1, tzinfo=UTC)) == date(2026, 10, 27)
    assert resolve_target_date("2026-07-15") == date(2026, 7, 15)
    with pytest.raises(ValueError, match="YYYY-MM-DD"):
        resolve_target_date("07/15/2026")


def test_status_is_the_lock_and_completed_date_is_idempotent(job_engine) -> None:
    target = date(2026, 7, 15)
    first = claim_job(job_engine, target)
    assert first.outcome == "claimed"
    assert first.run_id is not None
    assert has_processing_lock(job_engine)

    blocked = claim_job(job_engine, target + timedelta(days=1))
    assert blocked.outcome == "processing"

    update_job_run(job_engine, first.run_id, "completed")
    assert not has_processing_lock(job_engine)
    assert has_completed_for_date(job_engine, target)
    assert claim_job(job_engine, target).outcome == "completed"


def test_export_is_atomic_filtered_and_not_overwritten(job_engine, tmp_path: Path) -> None:
    target = date(2026, 7, 15)
    _insert_event(job_engine, datetime(2026, 7, 15, 12, tzinfo=UTC))
    _insert_event(job_engine, datetime(2026, 7, 16, 12, tzinfo=UTC))
    output = tmp_path / "raw" / "telemetry_2026-07-15.csv"

    assert export_telemetry_csv(job_engine, target, output) == (1, True)
    before = output.read_bytes()
    assert export_telemetry_csv(job_engine, target, output) == (1, False)
    assert output.read_bytes() == before

    with output.open(newline="", encoding="utf-8") as exported:
        rows = list(csv.DictReader(exported))
    assert len(rows) == 1
    assert rows[0]["event_type"] == "page_viewed"
    assert rows[0]["tags"] == '{"route":"/reporting"}'


def test_successful_run_records_completion_and_skips_duplicate(job_engine, tmp_path: Path) -> None:
    target = date(2026, 7, 15)
    _insert_event(job_engine, datetime(2026, 7, 15, 12, tzinfo=UTC))
    calls: list[str] = []

    first = run_nightly_export(
        target_date=target,
        engine=job_engine,
        raw_directory=tmp_path / "raw",
        pipeline_runner=lambda: calls.append("pipeline"),
    )
    second = run_nightly_export(
        target_date=target,
        engine=job_engine,
        raw_directory=tmp_path / "raw",
        pipeline_runner=lambda: calls.append("duplicate"),
    )

    assert first["status"] == "completed"
    assert first["rows_exported"] == 1
    assert second["outcome"] == "duplicate"
    assert calls == ["pipeline"]
    assert get_job_run(job_engine, first["run_id"])["status"] == "completed"


def test_failure_never_leaves_a_processing_zombie(job_engine, tmp_path: Path) -> None:
    target = date(2026, 7, 15)

    def fail_pipeline() -> None:
        raise RuntimeError("synthetic pipeline failure")

    with pytest.raises(RuntimeError, match="synthetic pipeline failure"):
        run_nightly_export(
            target_date=target,
            engine=job_engine,
            raw_directory=tmp_path / "raw",
            pipeline_runner=fail_pipeline,
        )

    with job_engine.connect() as connection:
        row = (
            connection.execute(select(job_runs).where(job_runs.c.target_date == target))
            .mappings()
            .one()
        )
    assert row.status == "failed"
    assert row.finished_at is not None
    assert row.error_message == "synthetic pipeline failure"
    assert not has_processing_lock(job_engine)


def test_two_instances_cannot_process_in_parallel(job_engine, tmp_path: Path) -> None:
    started = threading.Event()
    release = threading.Event()

    def slow_pipeline() -> None:
        started.set()
        assert release.wait(timeout=5)

    def first_instance() -> dict:
        return run_nightly_export(
            target_date=date(2026, 7, 15),
            engine=job_engine,
            raw_directory=tmp_path / "raw",
            pipeline_runner=slow_pipeline,
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        first_future = pool.submit(first_instance)
        assert started.wait(timeout=5)
        second = run_nightly_export(
            target_date=date(2026, 7, 16),
            engine=job_engine,
            raw_directory=tmp_path / "raw",
            pipeline_runner=lambda: pytest.fail("locked instance ran the pipeline"),
        )
        release.set()
        first = first_future.result(timeout=5)

    assert second["outcome"] == "locked"
    assert first["status"] == "completed"
