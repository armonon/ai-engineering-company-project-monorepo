"""Authenticated Celery task lifecycle endpoint."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from celery_app import celery_app
from security import get_current_user

router = APIRouter(prefix="/tasks", tags=["tasks"])


class TaskStatusResponse(BaseModel):
    task_id: str
    status: str
    result: Any | None = None
    error: str | None = None


def task_result(task_id: str):
    """Small seam for status lookup and deterministic acceptance tests."""

    return celery_app.AsyncResult(task_id)


def public_status(celery_state: str) -> str:
    """Map Celery's complete state vocabulary onto the required contract."""

    normalized = celery_state.upper()
    if normalized == "SUCCESS":
        return "success"
    if normalized == "FAILURE":
        return "failure"
    if normalized in {"STARTED", "RETRY", "RECEIVED"}:
        return "started"
    return "pending"


@router.get("/{task_id}", response_model=TaskStatusResponse)
def get_task_status(
    task_id: str,
    _caller=Depends(get_current_user),
) -> TaskStatusResponse:
    """Return live status and the result only after successful completion."""

    result = task_result(task_id)
    status = public_status(result.state)
    payload: Any | None = result.result if status == "success" else None
    error = str(result.result) if status == "failure" else None
    return TaskStatusResponse(task_id=task_id, status=status, result=payload, error=error)
