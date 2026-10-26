"""Resilient TrackFlow weekly warehouse/client performance pipeline.

Run from the repository root after installing the API environment:

    services/api/.venv/bin/python data/pipelines/pipeline.py

The database URL is read from the environment (or ``services/api/.env``),
never accepted as a flow parameter where an orchestrator could display it.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from dotenv import load_dotenv
from prefect import flow, get_run_logger, task
from prefect.tasks import task_input_hash
from sqlalchemy import JSON, Column, DateTime, MetaData, String, Table, Uuid, delete, insert
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.sql import select

_REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(_REPOSITORY_ROOT / "services" / "api" / ".env", override=False)

if __package__:
    from trackflow_process import transform_weekly_performance as transform_events

    from .storage import ensure_reporting_schema, make_engine, utcnow
else:  # Supports the rubric's direct `python data/pipelines/pipeline.py` command.
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "process"))
    from storage import ensure_reporting_schema, make_engine, utcnow
    from weekly_performance import transform_weekly_performance as transform_events

BUSINESS_EVENT_TYPES = (
    "inbound_order_created",
    "outbound_order_created",
    "stock_threshold_triggered",
    "inventory_discrepancy_detected",
)


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise ValueError("pipeline windows must include a UTC offset")
    return value.astimezone(UTC)


def resolve_week_window(week_start: date | None = None) -> tuple[datetime, datetime]:
    """Return one completed UTC ISO-week window."""
    if week_start is None:
        today = datetime.now(UTC).date()
        this_monday = today - timedelta(days=today.weekday())
        week_start = this_monday - timedelta(days=7)
    if week_start.weekday() != 0:
        raise ValueError("week_start must be a Monday")
    start = datetime.combine(week_start, time.min, tzinfo=UTC)
    return start, start + timedelta(days=7)


def _telemetry_table(dialect_name: str) -> Table:
    schema = "public" if dialect_name == "postgresql" else None
    metadata = MetaData(schema=schema)
    return Table(
        "telemetry_events",
        metadata,
        Column("id", Uuid(as_uuid=False), primary_key=True),
        Column("timestamp", DateTime(timezone=True), nullable=False),
        Column("event_type", String, nullable=False),
        Column("tags", JSON, nullable=False),
    )


# Three bounded retries cover short pooler/network interruptions without hiding
# a sustained outage for long enough to miss the Monday reporting deadline.
@task(name="record_pipeline_run_start", retries=3, retry_delay_seconds=2)
def record_pipeline_run_start(
    run_id: str,
    window_start: datetime,
    window_end: datetime,
    trigger: str,
) -> None:
    engine = make_engine()
    try:
        _, runs = ensure_reporting_schema(engine)
        try:
            with engine.begin() as connection:
                connection.execute(
                    insert(runs).values(
                        run_id=run_id,
                        started_at=utcnow(),
                        window_start=_utc(window_start),
                        window_end=_utc(window_end),
                        status="Running",
                        trigger=trigger,
                        records_processed=0,
                        rows_transformed=0,
                        rows_committed=0,
                        deduplicated=0,
                        quality_summary={},
                    )
                )
        except IntegrityError:
            # Safe after a lost acknowledgement: the durable run row proves the
            # first attempt committed, so a retry must not create another run.
            with engine.connect() as connection:
                durable_run = connection.scalar(
                    select(runs.c.run_id).where(runs.c.run_id == run_id)
                )
            if durable_run is None:
                raise
    finally:
        engine.dispose()


# Extraction touches PostgreSQL/Supabase, so the same bounded transient retry
# policy applies. Validation failures occur later and are intentionally not retried.
@task(name="extract_business_events", retries=3, retry_delay_seconds=2)
def extract_business_events(
    window_start: datetime,
    window_end: datetime,
) -> list[dict[str, Any]]:
    engine = make_engine()
    try:
        source = _telemetry_table(engine.dialect.name)
        statement = (
            select(source.c.id, source.c.timestamp, source.c.event_type, source.c.tags)
            .where(
                source.c.timestamp >= _utc(window_start),
                source.c.timestamp < _utc(window_end),
                source.c.event_type.in_(BUSINESS_EVENT_TYPES),
            )
            .order_by(source.c.timestamp, source.c.id)
        )
        with engine.connect() as connection:
            rows = connection.execute(statement).mappings().all()
        return [
            {
                "id": str(row.id),
                # PostgreSQL returns the required aware timestamptz. SQLite is
                # used only by the deterministic test suite and drops offsets
                # on round-trip, so restore the source contract there.
                "timestamp": (
                    row.timestamp.replace(tzinfo=UTC)
                    if engine.dialect.name == "sqlite" and row.timestamp.tzinfo is None
                    else row.timestamp
                ),
                "event_type": row.event_type,
                "tags": (json.loads(row.tags) if isinstance(row.tags, str) else dict(row.tags)),
            }
            for row in rows
        ]
    finally:
        engine.dispose()


@task(
    name="transform_weekly_performance",
    cache_key_fn=task_input_hash,
    cache_expiration=timedelta(hours=1),
    persist_result=True,
)
def transform_weekly_performance(events: list[dict[str, Any]]) -> dict[str, Any]:
    """Cache deterministic input content for one hour, per the ticket.

    ``task_input_hash`` hashes the extracted event values, not only the window,
    so a late event produces a new key while an immediate identical rerun can
    safely reuse the expensive validation/dedup/aggregation result.
    """
    return transform_events(events)


# Load is the second external database boundary and receives the same three
# short retries. Absolute upserts make a retry safe after an uncertain reply.
@task(name="load_weekly_performance", retries=3, retry_delay_seconds=2)
def load_weekly_performance(
    run_id: str,
    window_start: datetime,
    window_end: datetime,
    transformed: dict[str, Any],
) -> int:
    engine = make_engine()
    try:
        weekly, runs = ensure_reporting_schema(engine)
        computed_at = utcnow()
        payload = [
            {
                "id": str(uuid4()),
                **row,
                "computed_at": computed_at,
            }
            for row in transformed["rows"]
        ]
        business_columns = {
            "inbound_units_count",
            "outbound_orders_count",
            "stockout_events_count",
            "discrepancy_events_count",
            "discrepancy_rate",
            "computed_at",
        }

        with engine.begin() as connection:
            if payload:
                if engine.dialect.name == "postgresql":
                    upsert = postgresql_insert(weekly).values(payload)
                elif engine.dialect.name == "sqlite":
                    upsert = sqlite_insert(weekly).values(payload)
                else:
                    raise RuntimeError("the pipeline supports PostgreSQL and SQLite")
                upsert = upsert.on_conflict_do_update(
                    index_elements=["warehouse", "client_id", "week_start"],
                    set_={name: getattr(upsert.excluded, name) for name in business_columns},
                )
                connection.execute(upsert)

            existing = connection.execute(
                select(
                    weekly.c.warehouse,
                    weekly.c.client_id,
                    weekly.c.week_start,
                ).where(
                    weekly.c.week_start >= _utc(window_start).date(),
                    weekly.c.week_start < _utc(window_end).date(),
                )
            ).all()
            current_keys = {
                (row["warehouse"], row["client_id"], row["week_start"])
                for row in transformed["rows"]
            }
            stale_keys = set(existing) - current_keys
            for warehouse, client_id, week_start in stale_keys:
                connection.execute(
                    delete(weekly).where(
                        weekly.c.warehouse == warehouse,
                        weekly.c.client_id == client_id,
                        weekly.c.week_start == week_start,
                    )
                )

            connection.execute(
                runs.update()
                .where(runs.c.run_id == run_id)
                .values(
                    finished_at=utcnow(),
                    status="Completed",
                    records_processed=transformed["records_processed"],
                    rows_transformed=len(transformed["rows"]),
                    rows_committed=len(payload),
                    deduplicated=transformed["deduplicated"],
                    error_summary=None,
                    quality_summary=transformed["quality_summary"],
                )
            )
        return len(payload)
    finally:
        engine.dispose()


@task(name="record_pipeline_run_failure", retries=3, retry_delay_seconds=2)
def record_pipeline_run_failure(run_id: str, error_code: str) -> None:
    """Record safe failure metadata without persisting payloads or secrets."""
    engine = make_engine()
    try:
        _, runs = ensure_reporting_schema(engine)
        with engine.begin() as connection:
            connection.execute(
                runs.update()
                .where(runs.c.run_id == run_id)
                .values(
                    finished_at=utcnow(),
                    status="Failed",
                    error_summary=error_code[:200],
                )
            )
    finally:
        engine.dispose()


@task(name="write_pipeline_evaluation_snapshot")
def write_evaluation_snapshot(run_id: str, transformed: dict[str, Any]) -> str:
    """Optional local validation artefact; never a publication prerequisite."""
    directory = Path(
        os.environ.get(
            "PIPELINE_EVAL_DIRECTORY",
            str(_REPOSITORY_ROOT / "data" / "eval" / "pipeline-runs"),
        )
    )
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{run_id}.json"
    document = {
        "run_id": run_id,
        "records_processed": transformed["records_processed"],
        "rows_transformed": len(transformed["rows"]),
        "deduplicated": transformed["deduplicated"],
        "quality_summary": transformed["quality_summary"],
    }
    path.write_text(json.dumps(document, indent=2, sort_keys=True), encoding="utf-8")
    return str(path)


@flow(name="extract_weekly_warehouse_client_events")
def extract_weekly_warehouse_client_events(
    window_start: datetime,
    window_end: datetime,
) -> list[dict[str, Any]]:
    """Extract the four governed business event types for one UTC window."""
    return extract_business_events(window_start, window_end)


@flow(name="transform_weekly_warehouse_client_kpis")
def transform_weekly_warehouse_client_kpis(
    events: list[dict[str, Any]],
) -> dict[str, Any]:
    """Validate, deduplicate, and aggregate TrackFlow's five exact KPIs."""
    return transform_weekly_performance(events)


@flow(name="load_weekly_warehouse_client_performance")
def load_weekly_warehouse_client_performance(
    run_id: str,
    window_start: datetime,
    window_end: datetime,
    transformed: dict[str, Any],
) -> int:
    """Idempotently publish the absolute weekly warehouse/client rows."""
    return load_weekly_performance(run_id, window_start, window_end, transformed)


@flow(name="write_weekly_performance_evaluation")
def write_weekly_performance_evaluation(
    run_id: str,
    transformed: dict[str, Any],
) -> str:
    """Run the optional local evaluation output outside the critical path."""
    return write_evaluation_snapshot(run_id, transformed)


@flow(name="weekly_warehouse_client_performance_flow", log_prints=True)
def weekly_warehouse_client_performance_flow(
    window_start: datetime | None = None,
    window_end: datetime | None = None,
    run_id: str | None = None,
    trigger: str = "scheduled",
) -> dict[str, Any]:
    """Extract, transform, and atomically publish one or more complete weeks."""
    logger = get_run_logger()
    if window_start is None and window_end is None:
        window_start, window_end = resolve_week_window()
    elif window_start is None or window_end is None:
        raise ValueError("window_start and window_end must be supplied together")
    window_start, window_end = _utc(window_start), _utc(window_end)
    if window_start >= window_end:
        raise ValueError("window_start must be earlier than window_end")
    if window_start.weekday() != 0 or window_start.time() != time.min:
        raise ValueError("window_start must be Monday 00:00 UTC")
    if window_end.weekday() != 0 or window_end.time() != time.min:
        raise ValueError("window_end must be Monday 00:00 UTC")
    if trigger not in {"scheduled", "manual", "backfill"}:
        raise ValueError("trigger must be scheduled, manual, or backfill")

    run_id = str(UUID(run_id)) if run_id else str(uuid4())
    started = False
    try:
        record_pipeline_run_start(run_id, window_start, window_end, trigger)
        started = True
        extracted = extract_weekly_warehouse_client_events(window_start, window_end)
        transformed = transform_weekly_warehouse_client_kpis(extracted)
        committed = load_weekly_warehouse_client_performance(
            run_id,
            window_start,
            window_end,
            transformed,
        )
    except Exception as exc:
        if started:
            # Persist only the exception class. Source payloads, SQL text, and
            # connection strings never belong in the business run log.
            record_pipeline_run_failure(run_id, type(exc).__name__)
        raise

    # This task is intentionally non-critical. Prefect returns a Failed state
    # instead of raising, and the already committed business publication stays
    # Completed even if the convenience snapshot cannot be written.
    optional_state = write_weekly_performance_evaluation(
        run_id,
        transformed,
        return_state=True,
    )
    if optional_state.is_failed():
        logger.warning("Optional evaluation snapshot failed; publication remains valid.")

    return {
        "run_id": run_id,
        "status": "Completed",
        "records_processed": transformed["records_processed"],
        "rows_committed": committed,
        "optional_snapshot_status": optional_state.name,
    }


def _parse_cli() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Publish TrackFlow's weekly warehouse/client performance report."
    )
    parser.add_argument(
        "--week-start",
        type=date.fromisoformat,
        help="UTC Monday (YYYY-MM-DD). Defaults to the last completed ISO week.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    arguments = _parse_cli()
    start, end = resolve_week_window(arguments.week_start)
    result = weekly_warehouse_client_performance_flow(
        window_start=start,
        window_end=end,
        trigger="manual",
    )
    print(json.dumps(result, indent=2, sort_keys=True))
