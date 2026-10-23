"""Read-only query adapter used by the reporting HTTP module."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy import desc, func, select

from .storage import ensure_reporting_schema, make_engine


def _run_dict(row: Any) -> dict[str, Any]:
    return {
        "run_id": str(row.run_id),
        "status": row.status,
        "trigger": row.trigger,
        "started_at": row.started_at,
        "finished_at": row.finished_at,
        "window_start": row.window_start,
        "window_end": row.window_end,
        "records_processed": row.records_processed,
        "rows_transformed": row.rows_transformed,
        "rows_committed": row.rows_committed,
        "deduplicated": row.deduplicated,
        "error_summary": row.error_summary,
        "quality_summary": row.quality_summary or {},
    }


def get_latest_run() -> dict[str, Any] | None:
    engine = make_engine()
    try:
        _, runs = ensure_reporting_schema(engine)
        with engine.connect() as connection:
            row = (
                connection.execute(select(runs).order_by(desc(runs.c.started_at)).limit(1))
                .mappings()
                .first()
            )
        return _run_dict(row) if row is not None else None
    finally:
        engine.dispose()


def get_active_run(window_start: Any, window_end: Any) -> dict[str, Any] | None:
    engine = make_engine()
    try:
        _, runs = ensure_reporting_schema(engine)
        with engine.connect() as connection:
            row = (
                connection.execute(
                    select(runs)
                    .where(
                        runs.c.status == "Running",
                        runs.c.window_start == window_start,
                        runs.c.window_end == window_end,
                    )
                    .order_by(desc(runs.c.started_at))
                    .limit(1)
                )
                .mappings()
                .first()
            )
        return _run_dict(row) if row is not None else None
    finally:
        engine.dispose()


def get_weekly_performance(week_start: date | None = None) -> dict[str, Any]:
    engine = make_engine()
    try:
        weekly, _ = ensure_reporting_schema(engine)
        with engine.connect() as connection:
            selected_week = week_start
            if selected_week is None:
                selected_week = connection.scalar(select(func.max(weekly.c.week_start)))
            if selected_week is None:
                return {"week_start": None, "entries": []}

            rows = connection.execute(
                select(weekly)
                .where(weekly.c.week_start == selected_week)
                .order_by(weekly.c.warehouse, weekly.c.client_id)
            ).mappings()
            entries = [
                {
                    "warehouse": row.warehouse,
                    "client_id": row.client_id,
                    "inbound_units_count": row.inbound_units_count,
                    "outbound_orders_count": row.outbound_orders_count,
                    "stockout_events_count": row.stockout_events_count,
                    "discrepancy_events_count": row.discrepancy_events_count,
                    "discrepancy_rate": float(
                        row.discrepancy_rate
                        if isinstance(row.discrepancy_rate, Decimal)
                        else Decimal(str(row.discrepancy_rate))
                    ),
                }
                for row in rows
            ]
        return {"week_start": selected_week.isoformat(), "entries": entries}
    finally:
        engine.dispose()
