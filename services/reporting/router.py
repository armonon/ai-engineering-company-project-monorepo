"""The three application endpoints required by the pipeline briefing."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any
from uuid import UUID, uuid4

from celery_app import enqueue_weekly_performance_task
from fastapi import APIRouter, Depends, HTTPException, Query, status
from models import Role, UserInDB
from pydantic import BaseModel, ConfigDict
from security import get_current_user
from trackflow_pipeline.pipeline import resolve_week_window
from trackflow_pipeline.queries import (
    get_active_run,
    get_latest_run,
    get_weekly_performance,
)

router = APIRouter(prefix="/reporting", tags=["reporting"])


class PipelineRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    week_start: date | None = None


class PipelineRunMetadata(BaseModel):
    run_id: UUID
    status: str
    trigger: str
    started_at: datetime
    finished_at: datetime | None
    window_start: datetime
    window_end: datetime
    records_processed: int
    rows_transformed: int
    rows_committed: int
    deduplicated: int
    error_summary: str | None
    quality_summary: dict[str, Any]


class LatestPipelineRunResponse(BaseModel):
    run: PipelineRunMetadata | None


class PipelineRunAccepted(BaseModel):
    task_id: str | None = None
    run_id: UUID
    status: str
    window_start: datetime
    window_end: datetime
    status_url: str


class WeeklyPerformanceEntry(BaseModel):
    warehouse: str
    client_id: str
    inbound_units_count: int
    outbound_orders_count: int
    stockout_events_count: int
    discrepancy_events_count: int
    discrepancy_rate: float


class WeeklyPerformanceResponse(BaseModel):
    week_start: date | None
    entries: list[WeeklyPerformanceEntry]


def _service_unavailable(exc: RuntimeError) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail=("Business reporting is not configured. Set DATABASE_URL and try again."),
    )


@router.get(
    "/pipeline-runs/latest",
    response_model=LatestPipelineRunResponse,
    summary="Latest business pipeline run",
)
def latest_pipeline_run(
    _caller: UserInDB = Depends(get_current_user),
) -> dict:
    try:
        return {"run": get_latest_run()}
    except RuntimeError as exc:
        raise _service_unavailable(exc) from exc


@router.post(
    "/pipeline-runs",
    response_model=PipelineRunAccepted,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Trigger a completed-week business pipeline run",
)
def trigger_pipeline_run(
    payload: PipelineRunRequest,
    caller: UserInDB = Depends(get_current_user),
) -> dict:
    if caller.role not in {Role.ADMIN, Role.MANAGER}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only TrackFlow administrators and managers may trigger a pipeline run.",
        )
    try:
        window_start, window_end = resolve_week_window(payload.week_start)
        active = get_active_run(window_start, window_end)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise _service_unavailable(exc) from exc

    if active is not None:
        return {
            "run_id": active["run_id"],
            "status": active["status"],
            "window_start": active["window_start"],
            "window_end": active["window_end"],
            "status_url": "/reporting/pipeline-runs/latest",
        }

    run_id = str(uuid4())
    task_id = enqueue_weekly_performance_task(
        window_start=window_start,
        window_end=window_end,
        run_id=run_id,
        trigger="manual",
    )
    return {
        "task_id": task_id,
        "run_id": run_id,
        "status": "Accepted",
        "window_start": window_start,
        "window_end": window_end,
        "status_url": f"/tasks/{task_id}",
    }


@router.get(
    "/weekly-warehouse-client-performance",
    response_model=WeeklyPerformanceResponse,
    summary="Weekly Warehouse & Client Performance Report",
)
def weekly_warehouse_client_performance(
    week_start: date | None = Query(default=None),
    _caller: UserInDB = Depends(get_current_user),
) -> dict:
    if week_start is not None and week_start.weekday() != 0:
        raise HTTPException(status_code=422, detail="week_start must be a Monday")
    try:
        return get_weekly_performance(week_start)
    except RuntimeError as exc:
        raise _service_unavailable(exc) from exc
