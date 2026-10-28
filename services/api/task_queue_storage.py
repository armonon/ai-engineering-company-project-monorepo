"""Database-backed dead-letter storage for asynchronous Celery tasks."""

from __future__ import annotations

import os
from datetime import UTC, datetime
from threading import Lock

from sqlalchemy import (
    Column,
    DateTime,
    Engine,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    create_engine,
    insert,
    select,
    update,
)

metadata = MetaData()
dead_letter_tasks = Table(
    "dead_letter_tasks",
    metadata,
    Column("task_id", String(255), primary_key=True),
    Column("task_name", String(255), nullable=False),
    Column("attempt", Integer, nullable=False),
    Column("error_message", Text, nullable=False),
    Column("failed_at", DateTime(timezone=True), nullable=False),
)

_engine: Engine | None = None
_engine_url: str | None = None
_engine_lock = Lock()


def task_database_url() -> str:
    """Return the injected database URL without ever logging credentials."""

    value = os.environ.get("DATABASE_URL", "").strip()
    if not value:
        raise RuntimeError("DATABASE_URL is not configured for async task storage.")
    return value


def task_engine(url: str | None = None) -> Engine:
    """Return one cached engine per configured URL."""

    global _engine, _engine_url

    selected = url or task_database_url()
    with _engine_lock:
        if _engine is None or _engine_url != selected:
            if _engine is not None:
                _engine.dispose()
            options: dict = {"pool_pre_ping": True}
            if selected.startswith("sqlite:"):
                options["connect_args"] = {"check_same_thread": False}
            _engine = create_engine(selected, **options)
            _engine_url = selected
        return _engine


def ensure_dead_letter_schema(engine: Engine | None = None) -> Table:
    """Create the DLQ table independently from the inventory metadata."""

    selected = engine or task_engine()
    metadata.create_all(selected)
    return dead_letter_tasks


def record_dead_letter(
    *,
    task_id: str,
    task_name: str,
    attempt: int,
    error_message: str,
    engine: Engine | None = None,
) -> dict:
    """Insert or refresh the terminal failure record for one task."""

    selected = engine or task_engine()
    ensure_dead_letter_schema(selected)
    failed_at = datetime.now(UTC)
    values = {
        "task_name": task_name,
        "attempt": attempt,
        "error_message": error_message,
        "failed_at": failed_at,
    }
    with selected.begin() as connection:
        exists = connection.execute(
            select(dead_letter_tasks.c.task_id).where(dead_letter_tasks.c.task_id == task_id)
        ).scalar_one_or_none()
        if exists is None:
            connection.execute(insert(dead_letter_tasks).values(task_id=task_id, **values))
        else:
            connection.execute(
                update(dead_letter_tasks)
                .where(dead_letter_tasks.c.task_id == task_id)
                .values(**values)
            )
    return {"task_id": task_id, **values}


def get_dead_letter(task_id: str, engine: Engine | None = None) -> dict | None:
    """Return one DLQ entry for diagnostics and acceptance tests."""

    selected = engine or task_engine()
    ensure_dead_letter_schema(selected)
    with selected.connect() as connection:
        row = (
            connection.execute(
                select(dead_letter_tasks).where(dead_letter_tasks.c.task_id == task_id)
            )
            .mappings()
            .first()
        )
    return dict(row) if row is not None else None


def dispose_task_engine() -> None:
    """Dispose cached connections between tests or configuration changes."""

    global _engine, _engine_url
    with _engine_lock:
        if _engine is not None:
            _engine.dispose()
        _engine = None
        _engine_url = None
