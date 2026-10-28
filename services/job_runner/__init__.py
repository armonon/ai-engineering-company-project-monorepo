"""Persistent lifecycle and locking for independent TrackFlow background jobs.

``job_runs.status`` is the lock.  A partial unique index permits at most one
``processing`` row for a job name, while the per-date unique key makes a
completed nightly run idempotent.  No FastAPI application object is imported
here, so cron workers remain independent from the request-serving process.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Literal
from uuid import uuid4

from sqlalchemy import (
    CheckConstraint,
    Column,
    Date,
    DateTime,
    Engine,
    Index,
    MetaData,
    String,
    Table,
    Text,
    UniqueConstraint,
    Uuid,
    create_engine,
    insert,
    select,
    text,
    update,
)
from sqlalchemy.exc import IntegrityError

JOB_NAME = "nightly_export"
FINAL_STATUSES = {"completed", "failed"}

metadata = MetaData()
job_runs = Table(
    "job_runs",
    metadata,
    Column("id", Uuid(as_uuid=False), primary_key=True),
    Column("job_name", String(80), nullable=False),
    Column("target_date", Date, nullable=False),
    Column("status", String(16), nullable=False),
    Column("started_at", DateTime(timezone=True)),
    Column("finished_at", DateTime(timezone=True)),
    Column("error_message", Text),
    Column("created_at", DateTime(timezone=True), nullable=False),
    CheckConstraint(
        "status IN ('pending', 'processing', 'completed', 'failed')",
        name="ck_job_runs_status",
    ),
    UniqueConstraint("job_name", "target_date", name="uq_job_runs_job_target_date"),
)
Index("ix_job_runs_job_target_date", job_runs.c.job_name, job_runs.c.target_date)
Index(
    "uq_job_runs_one_processing_job",
    job_runs.c.job_name,
    unique=True,
    postgresql_where=text("status = 'processing'"),
    sqlite_where=text("status = 'processing'"),
)


def utcnow() -> datetime:
    return datetime.now(UTC)


def database_url() -> str:
    """Return the injected job database URL without logging credentials."""
    value = (
        os.environ.get("JOB_DATABASE_URL", "").strip() or os.environ.get("DATABASE_URL", "").strip()
    )
    if not value:
        raise RuntimeError("DATABASE_URL is not configured for the nightly background job.")
    return value


def make_engine(url: str | None = None) -> Engine:
    selected = url or database_url()
    options = {"pool_pre_ping": True}
    if selected.startswith("sqlite:"):
        options["connect_args"] = {"check_same_thread": False}
    return create_engine(selected, **options)


def ensure_job_schema(engine: Engine) -> Table:
    metadata.create_all(engine)
    return job_runs


@dataclass(frozen=True)
class ClaimResult:
    outcome: Literal["claimed", "processing", "completed"]
    run_id: str | None
    target_date: date


def get_job_run(engine: Engine, run_id: str) -> dict | None:
    with engine.connect() as connection:
        row = connection.execute(select(job_runs).where(job_runs.c.id == run_id)).mappings().first()
    return dict(row) if row is not None else None


def has_processing_lock(engine: Engine, job_name: str = JOB_NAME) -> bool:
    with engine.connect() as connection:
        return (
            connection.execute(
                select(job_runs.c.id)
                .where(
                    job_runs.c.job_name == job_name,
                    job_runs.c.status == "processing",
                )
                .limit(1)
            ).first()
            is not None
        )


def has_completed_for_date(
    engine: Engine,
    target_date: date,
    job_name: str = JOB_NAME,
) -> bool:
    with engine.connect() as connection:
        return (
            connection.execute(
                select(job_runs.c.id)
                .where(
                    job_runs.c.job_name == job_name,
                    job_runs.c.target_date == target_date,
                    job_runs.c.status == "completed",
                )
                .limit(1)
            ).first()
            is not None
        )


def create_job_run(
    engine: Engine,
    target_date: date,
    job_name: str = JOB_NAME,
) -> str:
    """Create the required initial ``pending`` state."""
    ensure_job_schema(engine)
    run_id = str(uuid4())
    with engine.begin() as connection:
        connection.execute(
            insert(job_runs).values(
                id=run_id,
                job_name=job_name,
                target_date=target_date,
                status="pending",
                created_at=utcnow(),
            )
        )
    return run_id


def claim_job(
    engine: Engine,
    target_date: date,
    job_name: str = JOB_NAME,
) -> ClaimResult:
    """Atomically acquire the status-based lock for one nightly run.

    The database constraints settle races between processes.  A conflicting
    claim is re-read after rollback and reported as either an active lock or
    an already-completed idempotent execution.
    """
    ensure_job_schema(engine)
    run_id = str(uuid4())
    now = utcnow()
    try:
        with engine.begin() as connection:
            active = connection.execute(
                select(job_runs.c.id)
                .where(
                    job_runs.c.job_name == job_name,
                    job_runs.c.status == "processing",
                )
                .limit(1)
            ).scalar_one_or_none()
            if active is not None:
                return ClaimResult("processing", str(active), target_date)

            existing = (
                connection.execute(
                    select(job_runs).where(
                        job_runs.c.job_name == job_name,
                        job_runs.c.target_date == target_date,
                    )
                )
                .mappings()
                .first()
            )
            if existing is not None and existing.status == "completed":
                return ClaimResult("completed", str(existing.id), target_date)

            if existing is None:
                connection.execute(
                    insert(job_runs).values(
                        id=run_id,
                        job_name=job_name,
                        target_date=target_date,
                        status="pending",
                        created_at=now,
                    )
                )
            else:
                run_id = str(existing.id)

            connection.execute(
                update(job_runs)
                .where(job_runs.c.id == run_id)
                .values(
                    status="processing",
                    started_at=now,
                    finished_at=None,
                    error_message=None,
                )
            )
        return ClaimResult("claimed", run_id, target_date)
    except IntegrityError:
        with engine.connect() as connection:
            active = connection.execute(
                select(job_runs.c.id)
                .where(
                    job_runs.c.job_name == job_name,
                    job_runs.c.status == "processing",
                )
                .limit(1)
            ).scalar_one_or_none()
            completed = connection.execute(
                select(job_runs.c.id)
                .where(
                    job_runs.c.job_name == job_name,
                    job_runs.c.target_date == target_date,
                    job_runs.c.status == "completed",
                )
                .limit(1)
            ).scalar_one_or_none()
        if completed is not None:
            return ClaimResult("completed", str(completed), target_date)
        return ClaimResult(
            "processing",
            str(active) if active is not None else None,
            target_date,
        )


def update_job_run(
    engine: Engine,
    run_id: str,
    status: Literal["completed", "failed"],
    *,
    error_message: str | None = None,
) -> None:
    """Finish a claimed run; a lost transition is an explicit error."""
    if status not in FINAL_STATUSES:
        raise ValueError("status must be completed or failed")
    safe_error = error_message[:2000] if error_message else None
    with engine.begin() as connection:
        result = connection.execute(
            update(job_runs)
            .where(job_runs.c.id == run_id, job_runs.c.status == "processing")
            .values(
                status=status,
                finished_at=utcnow(),
                error_message=safe_error if status == "failed" else None,
            )
        )
    if result.rowcount != 1:
        raise RuntimeError(f"job run {run_id} is not in processing status")


__all__ = [
    "JOB_NAME",
    "ClaimResult",
    "claim_job",
    "create_job_run",
    "database_url",
    "ensure_job_schema",
    "get_job_run",
    "has_completed_for_date",
    "has_processing_lock",
    "job_runs",
    "make_engine",
    "update_job_run",
]
