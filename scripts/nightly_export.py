#!/usr/bin/env python3
"""Export one UTC day of telemetry and launch TrackFlow's business pipeline.

Run from the repository root with ``python scripts/nightly_export.py``.  This
process never imports or starts FastAPI.  Cron invokes it independently from
the API server, and ``job_runs.status = 'processing'`` is its only lock.
"""

from __future__ import annotations

import csv
import json
import logging
import os
import shlex
import subprocess
import sys
from collections.abc import Callable
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any
from uuid import uuid4

from dotenv import load_dotenv
from sqlalchemy import JSON, Column, DateTime, MetaData, Numeric, Table, Text, Uuid, select
from sqlalchemy.engine import Engine

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SERVICES_ROOT = REPOSITORY_ROOT / "services"
if str(SERVICES_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVICES_ROOT))

from job_runner import (  # noqa: E402
    JOB_NAME,
    claim_job,
    ensure_job_schema,
    make_engine,
    update_job_run,
)

CSV_FIELDS = [
    "id",
    "timestamp",
    "service",
    "event_type",
    "level",
    "value",
    "message",
    "tags",
]

logger = logging.getLogger("trackflow.nightly_export")


def configure_logging() -> None:
    if logger.handlers:
        return
    handler = logging.StreamHandler()
    handler.setFormatter(
        logging.Formatter(
            "%(asctime)s job=%(job_name)s status=%(status)s %(levelname)s %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%SZ",
        )
    )
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    logging.Formatter.converter = __import__("time").gmtime


def log_event(level: int, status: str, message: str, *args: Any) -> None:
    logger.log(
        level,
        message,
        *args,
        extra={"job_name": JOB_NAME, "status": status},
    )


def resolve_target_date(
    value: str | None = None,
    *,
    now: datetime | None = None,
) -> date:
    raw = value if value is not None else os.environ.get("TARGET_DATE", "")
    if raw.strip():
        try:
            return date.fromisoformat(raw.strip())
        except ValueError as exc:
            raise ValueError("TARGET_DATE must use YYYY-MM-DD format") from exc
    current = (now or datetime.now(UTC)).astimezone(UTC)
    return current.date() - timedelta(days=1)


def telemetry_table() -> Table:
    metadata = MetaData()
    return Table(
        "telemetry_events",
        metadata,
        Column("id", Uuid(as_uuid=False), primary_key=True),
        Column("timestamp", DateTime(timezone=True), nullable=False),
        Column("service", Text, nullable=False),
        Column("event_type", Text, nullable=False),
        Column("level", Text, nullable=False),
        Column("value", Numeric),
        Column("message", Text),
        Column("tags", JSON, nullable=False),
    )


def _csv_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.astimezone(UTC).isoformat()
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (dict, list)):
        return json.dumps(value, sort_keys=True, separators=(",", ":"))
    return str(value)


def csv_path_for(target_date: date, raw_directory: Path | None = None) -> Path:
    directory = raw_directory or REPOSITORY_ROOT / "data" / "raw"
    return directory / f"telemetry_{target_date.isoformat()}.csv"


def export_telemetry_csv(
    engine: Engine,
    target_date: date,
    destination: Path,
) -> tuple[int, bool]:
    """Atomically create the audit CSV once; return ``(rows, created)``."""
    if destination.exists():
        with destination.open(newline="", encoding="utf-8") as existing:
            return max(sum(1 for _ in existing) - 1, 0), False

    start = datetime.combine(target_date, time.min, tzinfo=UTC)
    end = start + timedelta(days=1)
    source = telemetry_table()
    with engine.connect() as connection:
        rows = (
            connection.execute(
                select(*(source.c[field] for field in CSV_FIELDS))
                .where(source.c.timestamp >= start, source.c.timestamp < end)
                .order_by(source.c.timestamp, source.c.id)
            )
            .mappings()
            .all()
        )

    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(f".{destination.name}.{uuid4().hex}.tmp")
    try:
        with temporary.open("x", newline="", encoding="utf-8") as output:
            writer = csv.DictWriter(output, fieldnames=CSV_FIELDS)
            writer.writeheader()
            for row in rows:
                writer.writerow({field: _csv_value(row[field]) for field in CSV_FIELDS})
        temporary.replace(destination)
    finally:
        if temporary.exists():
            temporary.unlink()
    return len(rows), True


def pipeline_command() -> list[str]:
    override = os.environ.get("PIPELINE_COMMAND", "").strip()
    if override:
        command = shlex.split(override)
        if not command:
            raise ValueError("PIPELINE_COMMAND cannot be empty")
        return command
    return [sys.executable, str(REPOSITORY_ROOT / "data" / "pipelines" / "pipeline.py")]


def run_pipeline() -> None:
    subprocess.run(
        pipeline_command(),
        cwd=REPOSITORY_ROOT,
        check=True,
        env=os.environ.copy(),
    )


def run_nightly_export(
    *,
    target_date: date | None = None,
    engine: Engine | None = None,
    raw_directory: Path | None = None,
    pipeline_runner: Callable[[], None] = run_pipeline,
) -> dict[str, Any]:
    """Claim, export, run the pipeline, and persist the terminal state."""
    selected_date = target_date or resolve_target_date()
    owns_engine = engine is None
    database = engine or make_engine()
    ensure_job_schema(database)
    claim = claim_job(database, selected_date)

    if claim.outcome == "processing":
        log_event(logging.INFO, "processing", "another instance holds the lock; skipped")
        return {"status": "processing", "outcome": "locked", "target_date": selected_date}
    if claim.outcome == "completed":
        log_event(logging.INFO, "completed", "duplicate target date; skipped")
        return {"status": "completed", "outcome": "duplicate", "target_date": selected_date}

    assert claim.run_id is not None
    destination = csv_path_for(selected_date, raw_directory)
    log_event(logging.INFO, "processing", "execution started target_date=%s", selected_date)
    try:
        row_count, created = export_telemetry_csv(database, selected_date, destination)
        log_event(
            logging.INFO,
            "processing",
            "telemetry export rows=%d csv_created=%s",
            row_count,
            created,
        )
        pipeline_runner()
        update_job_run(database, claim.run_id, "completed")
        log_event(logging.INFO, "completed", "execution finished")
        return {
            "status": "completed",
            "outcome": "ran",
            "target_date": selected_date,
            "rows_exported": row_count,
            "csv_path": str(destination),
            "run_id": claim.run_id,
        }
    except Exception as exc:
        update_job_run(database, claim.run_id, "failed", error_message=str(exc))
        log_event(logging.ERROR, "failed", "execution failed: %s", type(exc).__name__)
        raise
    finally:
        if owns_engine:
            database.dispose()


def main() -> int:
    configure_logging()
    load_dotenv(REPOSITORY_ROOT / "services" / "api" / ".env")
    try:
        result = run_nightly_export()
    except Exception:
        return 1
    # Safe summary only: no database URL, event payload, or tags.
    print(
        json.dumps(
            {
                key: value.isoformat() if isinstance(value, date) else value
                for key, value in result.items()
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
