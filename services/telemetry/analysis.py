"""SQL-bounded, vectorised technical metrics over the approved event catalogue.

All periods are half-open UTC intervals. No writes, cache, implicit clock or
business KPIs live here. Empty populations return [], never invented zero days.
"""

from collections.abc import Sequence
from datetime import datetime
from typing import Any

import pandas as pd
from sqlalchemy import JSON, DateTime, Numeric, String, column, select, table
from sqlalchemy.engine import Connection

EVENTS = table(
    "telemetry_events",
    column("timestamp", DateTime(timezone=True)),
    column("event_type", String),
    column("service", String),
    column("level", String),
    column("value", Numeric),
    column("tags", JSON),
)


def _load(
    connection: Connection,
    start_date: datetime,
    end_date: datetime,
    event_types: Sequence[str],
) -> pd.DataFrame:
    """Both time and event-type predicates are parameterized SQL, never pandas filters."""
    query = select(EVENTS).where(
        EVENTS.c.timestamp >= start_date,
        EVENTS.c.timestamp < end_date,
        EVENTS.c.event_type.in_(event_types),
    )
    return pd.read_sql(query, connection)


def _dates(frame: pd.DataFrame) -> pd.DataFrame:
    frame["timestamp"] = pd.to_datetime(frame["timestamp"], utc=True)
    frame["date"] = frame["timestamp"].dt.strftime("%Y-%m-%d")
    return frame


def events_per_day(
    connection: Connection,
    start_date: datetime,
    end_date: datetime,
    event_types: Sequence[str],
) -> list[dict[str, Any]]:
    """Event traffic by UTC day and catalogue type (not inventory quantity or revenue)."""
    frame = _load(connection, start_date, end_date, event_types)
    frame = _dates(frame.dropna(subset=["event_type"]))
    return (
        frame.groupby(["date", "event_type"])["timestamp"]
        .count()
        .rename("count")
        .reset_index()
        .to_dict(orient="records")
    )


def error_rate_by_day(
    connection: Connection,
    start_date: datetime,
    end_date: datetime,
    event_types: Sequence[str],
) -> list[dict[str, Any]]:
    """Error-level event share by day/service, not an HTTP request failure probability."""
    frame = _load(connection, start_date, end_date, event_types)
    frame = frame.dropna(subset=["service"])
    frame["is_error"] = frame["level"].eq("error")
    frame = _dates(frame)
    grouped = frame.groupby(["date", "service"]).agg(
        total_events=("event_type", "count"), error_events=("is_error", "sum")
    )
    grouped["error_rate"] = grouped["error_events"] / grouped["total_events"]
    return grouped.reset_index().to_dict(orient="records")


def latency_by_endpoint(
    connection: Connection, start_date: datetime, end_date: datetime
) -> list[dict[str, Any]]:
    """Mean API duration (ms) per UTC day and every non-null endpoint template."""
    frame = _load(connection, start_date, end_date, ["api_latency_recorded"])
    dimensions = pd.json_normalize(frame["tags"])
    frame["endpoint_template"] = dimensions.reindex(columns=["endpoint_template"])[
        "endpoint_template"
    ]
    frame["duration_ms"] = pd.to_numeric(frame["value"], errors="coerce")
    frame = frame.dropna(subset=["endpoint_template", "duration_ms"])
    frame = frame.loc[
        frame["duration_ms"].ge(0) & ~frame["duration_ms"].isin([float("inf"), -float("inf")])
    ]
    frame = _dates(frame)
    return (
        frame.groupby(["date", "endpoint_template"])
        .agg(samples=("duration_ms", "count"), mean_duration_ms=("duration_ms", "mean"))
        .reset_index()
        .to_dict(orient="records")
    )


def auth_failure_rate(
    connection: Connection, start_date: datetime, end_date: datetime
) -> list[dict[str, Any]]:
    """Use TrackFlow's actual login_failed/login_succeeded names, never invented aliases."""
    frame = _load(connection, start_date, end_date, ["login_failed", "login_succeeded"])
    frame["failed"] = frame["event_type"].eq("login_failed")
    frame = _dates(frame)
    grouped = frame.groupby("date").agg(
        attempts=("event_type", "count"), failures=("failed", "sum")
    )
    grouped["failure_rate"] = grouped["failures"] / grouped["attempts"]
    return grouped.reset_index().to_dict(orient="records")
