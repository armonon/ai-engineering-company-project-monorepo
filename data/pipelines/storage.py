"""Database schema and connection helpers for the reporting pipeline."""

from __future__ import annotations

import os
from datetime import UTC, datetime
from functools import lru_cache
from typing import Any
from uuid import uuid4

from sqlalchemy import (
    JSON,
    BigInteger,
    Column,
    Date,
    DateTime,
    Integer,
    MetaData,
    Numeric,
    String,
    Table,
    Text,
    UniqueConstraint,
    Uuid,
    create_engine,
    text,
)
from sqlalchemy.engine import Engine


def utcnow() -> datetime:
    return datetime.now(UTC)


def database_url() -> str:
    """Return the injected database URL without ever logging its value."""
    value = (
        os.environ.get("PIPELINE_DATABASE_URL", "").strip()
        or os.environ.get("DATABASE_URL", "").strip()
    )
    if not value:
        raise RuntimeError(
            "DATABASE_URL is not configured for the reporting pipeline. "
            "Set it in services/api/.env or the process environment."
        )
    return value


def make_engine() -> Engine:
    return create_engine(database_url(), pool_pre_ping=True)


@lru_cache(maxsize=2)
def reporting_tables(schema: str | None) -> tuple[MetaData, Table, Table]:
    metadata = MetaData(schema=schema)
    weekly = Table(
        "weekly_warehouse_client_performance",
        metadata,
        Column("id", Uuid(as_uuid=False), primary_key=True, default=lambda: str(uuid4())),
        Column("warehouse", Text, nullable=False),
        Column("client_id", Text, nullable=False),
        Column("week_start", Date, nullable=False),
        Column("inbound_units_count", Integer, nullable=False, default=0),
        Column("outbound_orders_count", Integer, nullable=False, default=0),
        Column("stockout_events_count", Integer, nullable=False, default=0),
        Column("discrepancy_events_count", Integer, nullable=False, default=0),
        Column("discrepancy_rate", Numeric, nullable=False, default=0),
        Column("computed_at", DateTime(timezone=True), nullable=False, default=utcnow),
        UniqueConstraint(
            "warehouse",
            "client_id",
            "week_start",
            name="uq_weekly_warehouse_client_performance_grain",
        ),
    )
    runs = Table(
        "pipeline_runs",
        metadata,
        Column("run_id", Uuid(as_uuid=False), primary_key=True),
        Column("started_at", DateTime(timezone=True), nullable=False),
        Column("finished_at", DateTime(timezone=True)),
        Column("window_start", DateTime(timezone=True), nullable=False),
        Column("window_end", DateTime(timezone=True), nullable=False),
        Column("status", String(16), nullable=False),
        Column("trigger", String(16), nullable=False),
        Column("records_processed", BigInteger, nullable=False, default=0),
        Column("rows_transformed", BigInteger, nullable=False, default=0),
        Column("rows_committed", BigInteger, nullable=False, default=0),
        Column("deduplicated", BigInteger, nullable=False, default=0),
        Column("error_summary", Text),
        Column("quality_summary", JSON, nullable=False, default=dict),
    )
    return metadata, weekly, runs


def tables_for(engine: Engine) -> tuple[Table, Table]:
    schema = "reporting" if engine.dialect.name == "postgresql" else None
    _, weekly, runs = reporting_tables(schema)
    return weekly, runs


def ensure_reporting_schema(engine: Engine) -> tuple[Table, Table]:
    """Create the dedicated reporting schema and its two owned tables."""
    schema = "reporting" if engine.dialect.name == "postgresql" else None
    metadata, weekly, runs = reporting_tables(schema)
    if schema is not None:
        with engine.begin() as connection:
            connection.execute(text("CREATE SCHEMA IF NOT EXISTS reporting"))
    metadata.create_all(engine)
    return weekly, runs


def json_safe(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.astimezone(UTC).isoformat()
    return value
