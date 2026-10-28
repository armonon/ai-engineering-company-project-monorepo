"""Acceptance coverage for Redis/Celery task offloading and dead letters."""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine

from celery_app import TASK_NAME, retry_countdown, weekly_performance_pipeline_task
from task_queue_storage import (
    get_dead_letter,
    record_dead_letter,
)


def test_retry_backoff_increases_exponentially() -> None:
    assert [retry_countdown(attempt) for attempt in (1, 2, 3)] == [1, 2, 4]
    assert weekly_performance_pipeline_task.max_retries == 3
    assert weekly_performance_pipeline_task.acks_late is True
    assert weekly_performance_pipeline_task.app.conf.task_acks_on_failure_or_timeout is False
    assert weekly_performance_pipeline_task.soft_time_limit == 300
    assert weekly_performance_pipeline_task.time_limit == 330


def test_dead_letter_is_durable_and_updates_one_task(tmp_path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'dlq.db'}")
    record_dead_letter(
        task_id="task-1",
        task_name=TASK_NAME,
        attempt=3,
        error_message="first failure",
        engine=engine,
    )
    record_dead_letter(
        task_id="task-1",
        task_name=TASK_NAME,
        attempt=3,
        error_message="final failure",
        engine=engine,
    )

    row = get_dead_letter("task-1", engine)
    assert row is not None
    assert row["attempt"] == 3
    assert row["error_message"] == "final failure"
    assert isinstance(row["failed_at"], datetime)
    engine.dispose()


@pytest.mark.parametrize(
    ("celery_state", "expected"),
    [
        ("PENDING", "pending"),
        ("RECEIVED", "started"),
        ("STARTED", "started"),
        ("RETRY", "started"),
        ("SUCCESS", "success"),
        ("FAILURE", "failure"),
        ("REVOKED", "pending"),
    ],
)
def test_public_task_status_contract(celery_state, expected) -> None:
    from routers.tasks import public_status

    assert public_status(celery_state) == expected


def test_task_status_endpoint_returns_result_only_on_success(signed_in, monkeypatch) -> None:
    from routers import tasks

    monkeypatch.setattr(
        tasks,
        "task_result",
        lambda _task_id: SimpleNamespace(state="SUCCESS", result={"rows_committed": 4}),
    )
    response = signed_in.get("/tasks/task-123")
    assert response.status_code == 200
    assert response.json() == {
        "task_id": "task-123",
        "status": "success",
        "result": {"rows_committed": 4},
        "error": None,
    }


def test_task_status_endpoint_surfaces_failure_without_result(signed_in, monkeypatch) -> None:
    from routers import tasks

    monkeypatch.setattr(
        tasks,
        "task_result",
        lambda _task_id: SimpleNamespace(state="FAILURE", result=RuntimeError("pipeline failed")),
    )
    response = signed_in.get("/tasks/task-456")
    assert response.status_code == 200
    assert response.json() == {
        "task_id": "task-456",
        "status": "failure",
        "result": None,
        "error": "pipeline failed",
    }


def test_task_message_is_lightweight_and_success_is_logged(monkeypatch, caplog) -> None:
    import celery_app as queue

    calls: list[dict] = []
    monkeypatch.setattr(
        queue,
        "submit_weekly_performance_run",
        lambda **kwargs: calls.append(kwargs) or {"status": "Completed", "rows_committed": 2},
    )
    with caplog.at_level("INFO", logger="trackflow.tasks"):
        result = weekly_performance_pipeline_task.apply(
            task_id="success-task",
            kwargs={
                "run_id": "run-123",
                "window_start": datetime(2026, 10, 5, tzinfo=UTC).isoformat(),
                "window_end": datetime(2026, 10, 12, tzinfo=UTC).isoformat(),
                "trigger": "manual",
            },
        )

    assert result.successful()
    assert result.result["rows_committed"] == 2
    assert calls[0]["run_id"] == "run-123"
    assert "task_id=success-task" in caplog.text
    assert "status=success" in caplog.text


def test_third_failure_is_recorded_in_dlq(monkeypatch, caplog) -> None:
    import celery_app as queue

    dead_letters: list[dict] = []

    def fail(**_kwargs):
        raise RuntimeError("intentional acceptance failure")

    monkeypatch.setattr(queue, "submit_weekly_performance_run", fail)
    monkeypatch.setattr(
        queue,
        "record_dead_letter",
        lambda **kwargs: dead_letters.append(kwargs),
    )
    weekly_performance_pipeline_task.push_request(id="failed-task", retries=2)
    try:
        with caplog.at_level("ERROR", logger="trackflow.tasks"):
            with pytest.raises(RuntimeError, match="intentional acceptance failure"):
                weekly_performance_pipeline_task.run(
                    run_id="run-456",
                    window_start=datetime(2026, 10, 5, tzinfo=UTC).isoformat(),
                    window_end=datetime(2026, 10, 12, tzinfo=UTC).isoformat(),
                    trigger="manual",
                )
    finally:
        weekly_performance_pipeline_task.pop_request()

    assert dead_letters == [
        {
            "task_id": "failed-task",
            "task_name": TASK_NAME,
            "attempt": 3,
            "error_message": "intentional acceptance failure",
        }
    ]
    assert "attempt=3" in caplog.text
    assert "error=intentional acceptance failure" in caplog.text


def test_compose_declares_shared_redis_worker_and_flower() -> None:
    compose = (__import__("pathlib").Path(__file__).parents[3] / "docker-compose.yml").read_text()
    assert "image: redis:7.4-alpine" in compose
    assert "--maxmemory-policy noeviction" in compose
    assert "REDIS_URL: ${REDIS_URL:-redis://redis:6379/0}" in compose
    assert "celery -A celery_app:celery_app worker" in compose
    assert "celery -A celery_app:celery_app flower --port=5555" in compose
    assert '"5555:5555"' in compose
