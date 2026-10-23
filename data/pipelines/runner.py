"""Small import boundary used by the API's background-task submission."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from .pipeline import weekly_warehouse_client_performance_flow


def submit_weekly_performance_run(
    *,
    window_start: datetime,
    window_end: datetime,
    run_id: str,
    trigger: str = "manual",
) -> dict[str, Any]:
    return weekly_warehouse_client_performance_flow(
        window_start=window_start,
        window_end=window_end,
        run_id=run_id,
        trigger=trigger,
    )
