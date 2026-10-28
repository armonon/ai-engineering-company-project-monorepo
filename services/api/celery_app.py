"""TrackFlow Celery producer/consumer configuration and heavy pipeline task."""

from __future__ import annotations

import logging
import os
import time
from datetime import datetime
from typing import Any

from celery import Celery
from trackflow_pipeline.runner import submit_weekly_performance_run

from task_queue_storage import record_dead_letter

logger = logging.getLogger("trackflow.tasks")
TASK_NAME = "trackflow.weekly_performance_pipeline"


def redis_url() -> str:
    """Broker/backend URL injected by the environment."""

    return os.environ.get("REDIS_URL", "redis://localhost:6379/0").strip()


celery_app = Celery("trackflow", broker=redis_url(), backend=redis_url())
celery_app.conf.update(
    task_track_started=True,
    worker_send_task_events=True,
    task_send_sent_event=True,
    task_acks_late=True,
    task_acks_on_failure_or_timeout=False,
    task_reject_on_worker_lost=True,
    result_expires=86_400,
    broker_transport_options={"visibility_timeout": 3_600},
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
)


def retry_countdown(attempt: int) -> int:
    """Exponential delay after attempt 1: 1, 2, then terminal failure."""

    return 2 ** max(0, attempt - 1)


@celery_app.task(
    bind=True,
    name=TASK_NAME,
    max_retries=3,
    track_started=True,
    acks_late=True,
    soft_time_limit=300,
    time_limit=330,
)
def weekly_performance_pipeline_task(
    self,
    *,
    run_id: str,
    window_start: str,
    window_end: str,
    trigger: str = "manual",
) -> dict[str, Any]:
    """Run the existing reporting pipeline outside the FastAPI process.

    The message carries only identifiers and ISO timestamps. The worker fetches
    source rows from the configured database instead of receiving a large batch.
    """

    task_id = str(self.request.id)
    attempt = int(self.request.retries) + 1
    started = time.monotonic()
    try:
        result = submit_weekly_performance_run(
            run_id=run_id,
            window_start=datetime.fromisoformat(window_start),
            window_end=datetime.fromisoformat(window_end),
            trigger=trigger,
        )
    except Exception as exc:
        duration = time.monotonic() - started
        logger.exception(
            "task_id=%s attempt=%d status=failure duration_seconds=%.3f error=%s",
            task_id,
            attempt,
            duration,
            exc,
        )
        if attempt >= 3:
            record_dead_letter(
                task_id=task_id,
                task_name=TASK_NAME,
                attempt=attempt,
                error_message=str(exc),
            )
            raise
        countdown = retry_countdown(attempt)
        logger.warning(
            "task_id=%s attempt=%d status=retry countdown_seconds=%d error=%s",
            task_id,
            attempt,
            countdown,
            exc,
        )
        raise self.retry(exc=exc, countdown=countdown) from exc

    duration = time.monotonic() - started
    logger.info(
        "task_id=%s attempt=%d status=success duration_seconds=%.3f",
        task_id,
        attempt,
        duration,
    )
    return result


def enqueue_weekly_performance_task(
    *,
    run_id: str,
    window_start: datetime,
    window_end: datetime,
    trigger: str,
) -> str:
    """Publish one lightweight task and return its broker identifier."""

    result = weekly_performance_pipeline_task.apply_async(
        kwargs={
            "run_id": run_id,
            "window_start": window_start.isoformat(),
            "window_end": window_end.isoformat(),
            "trigger": trigger,
        }
    )
    return str(result.id)
