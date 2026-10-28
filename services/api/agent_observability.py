"""Persistent TrackFlow agent/flow/task graph and process-local SSE fan-out."""

from __future__ import annotations

import queue
import threading
from contextlib import contextmanager
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from sqlmodel import Session, select

from models import (
    ObservabilityEvent,
    ObservedAgent,
    ObservedFlow,
    ObservedFlowAgent,
    ObservedTask,
)

AGENT_REGISTRY = {
    "first_line_cx": {
        "name": "First-line CX agent",
        "agent_type": "single_agent_conversational",
        "owner_area": "Valentina Cruz — Customer Experience",
        "flow_types": ["chat_session"],
    },
    "rfp_pipeline": {
        "name": "Commercial proposal pipeline",
        "agent_type": "multi_agent_workflow",
        "owner_area": "Miguel Torres — Commercial",
        "flow_types": ["rfp_workflow"],
    },
}

ACTION_TYPES = {"query", "tool_call", "draft_start", "write", "evaluate", "deliver"}
_subscribers: set[queue.Queue[dict[str, Any]]] = set()
_subscriber_lock = threading.Lock()


def _now() -> datetime:
    return datetime.now(UTC)


def ensure_registered_agents(session: Session) -> None:
    for agent_id, definition in AGENT_REGISTRY.items():
        if session.get(ObservedAgent, agent_id) is None:
            session.add(ObservedAgent(agent_id=agent_id, **definition))
    session.commit()


def available_actions(status: str, needs_intervention: bool) -> list[str]:
    actions = {
        "idle": ["start"],
        "running": ["pause", "cancel"],
        "paused": ["resume", "cancel"],
        "waiting_for_human": ["inspect"],
        "completed": ["inspect", "restart"],
        "failed": ["inspect", "restart"],
    }.get(status, ["inspect"])
    return [*actions, "intervene"] if needs_intervention and "intervene" not in actions else actions


def _publish(event: dict[str, Any]) -> None:
    with _subscriber_lock:
        subscribers = tuple(_subscribers)
    for subscriber in subscribers:
        subscriber.put_nowait(event)


def emit_event(session: Session, event_name: str, data: dict[str, Any]) -> int:
    event = ObservabilityEvent(event_name=event_name, data=data)
    session.add(event)
    session.commit()
    session.refresh(event)
    payload = {"id": event.id, "event": event_name, "data": data}
    _publish(payload)
    return int(event.id)


@contextmanager
def subscribe() -> Any:
    subscriber: queue.Queue[dict[str, Any]] = queue.Queue()
    with _subscriber_lock:
        _subscribers.add(subscriber)
    try:
        yield subscriber
    finally:
        with _subscriber_lock:
            _subscribers.discard(subscriber)


def start_flow(
    session: Session,
    *,
    flow_id: str,
    flow_type: str,
    triggered_by: str,
    agent_ids: list[str],
) -> ObservedFlow:
    ensure_registered_agents(session)
    flow = session.get(ObservedFlow, flow_id)
    if flow is None:
        flow = ObservedFlow(
            flow_id=flow_id,
            flow_type=flow_type,
            status="running",
            triggered_by=triggered_by,
        )
        session.add(flow)
    for agent_id in agent_ids:
        if session.get(ObservedAgent, agent_id) is None:
            raise ValueError(f"Unknown observed agent {agent_id!r}")
        existing = session.exec(
            select(ObservedFlowAgent).where(
                ObservedFlowAgent.flow_id == flow_id,
                ObservedFlowAgent.agent_id == agent_id,
            )
        ).first()
        if existing is None:
            session.add(
                ObservedFlowAgent(flow_id=flow_id, agent_id=agent_id, status="running")
            )
        agent = session.get(ObservedAgent, agent_id)
        assert agent is not None
        agent.current_status = "running"
        agent.updated_at = _now()
        session.add(agent)
    session.commit()
    for agent_id in agent_ids:
        emit_event(
            session,
            "agent_status_changed",
            {"agent_id": agent_id, "flow_id": flow_id, "status": "running"},
        )
    return flow


def record_task(
    session: Session,
    *,
    flow_id: str,
    agent_id: str,
    action_type: str,
    trigger: str,
    department_id: str | None = None,
    payload: dict[str, Any] | None = None,
    task_id: str | None = None,
    previous_task_id: str | None = None,
) -> ObservedTask:
    if action_type not in ACTION_TYPES:
        raise ValueError(f"Unsupported TrackFlow action_type {action_type!r}")
    if session.get(ObservedFlow, flow_id) is None:
        raise ValueError(f"Unknown flow {flow_id!r}")
    if session.get(ObservedAgent, agent_id) is None:
        raise ValueError(f"Unknown agent {agent_id!r}")
    task_id = task_id or f"task_{uuid4().hex}"
    task = ObservedTask(
        task_id=task_id,
        flow_id=flow_id,
        agent_id=agent_id,
        action_type=action_type,
        trigger=trigger,
        department_id=department_id,
        payload=payload or {},
        previous_task_id=previous_task_id,
    )
    if previous_task_id:
        previous = session.get(ObservedTask, previous_task_id)
        if previous is None or previous.flow_id != flow_id:
            raise ValueError("previous_task_id must identify a task in the same flow")
        previous.next_task_id = task_id
        previous.derived_task_ids = [*previous.derived_task_ids, task_id]
        session.add(previous)
    session.add(task)
    session.commit()
    session.refresh(task)
    data = {
        "agent_id": agent_id,
        "flow_id": flow_id,
        "task_id": task.task_id,
        "action_type": action_type,
    }
    if department_id:
        data["department_id"] = department_id
    emit_event(session, "agent_step", data)
    return task


def change_status(
    session: Session,
    *,
    flow_id: str,
    agent_id: str,
    status: str,
    needs_intervention: bool | None = None,
) -> None:
    agent = session.get(ObservedAgent, agent_id)
    flow = session.get(ObservedFlow, flow_id)
    participation = session.exec(
        select(ObservedFlowAgent).where(
            ObservedFlowAgent.flow_id == flow_id,
            ObservedFlowAgent.agent_id == agent_id,
        )
    ).first()
    if agent is None or flow is None or participation is None:
        raise ValueError("Unknown flow/agent participation")
    agent.current_status = status
    agent.updated_at = _now()
    if needs_intervention is not None:
        agent.needs_intervention = needs_intervention
    participation.status = status
    if status in {"completed", "failed", "cancelled"}:
        flow.status = status
        flow.completed_at = _now()
    session.add(agent)
    session.add(participation)
    session.add(flow)
    session.commit()
    emit_event(
        session,
        "agent_status_changed",
        {"agent_id": agent_id, "flow_id": flow_id, "status": status},
    )


def refresh_intervention_flags(session: Session, retry_limit: int = 3) -> None:
    now = _now()
    for agent_id in AGENT_REGISTRY:
        agent = session.get(ObservedAgent, agent_id)
        if agent is None:
            continue
        needs_intervention = False
        latest = session.exec(
            select(ObservedTask)
            .where(ObservedTask.agent_id == agent_id)
            .order_by(ObservedTask.created_at.desc())
        ).first()
        latest_at = (
            latest.created_at.replace(tzinfo=latest.created_at.tzinfo or UTC)
            if latest
            else now
        )
        if (
            agent_id == "first_line_cx"
            and latest
            and latest.action_type in {"query", "tool_call"}
            and (now - latest_at).total_seconds() > 20
        ):
            needs_intervention = True
        if agent_id == "rfp_pipeline" and latest:
            evaluations = session.exec(
                select(ObservedTask).where(
                    ObservedTask.flow_id == latest.flow_id,
                    ObservedTask.agent_id == agent_id,
                    ObservedTask.action_type == "evaluate",
                )
            ).all()
            failed = [task for task in evaluations if task.payload.get("overall_pass") is False]
            needs_intervention = len(failed) > retry_limit
        if agent.needs_intervention != needs_intervention:
            agent.needs_intervention = needs_intervention
            agent.updated_at = now
            session.add(agent)
    session.commit()


def serialize_task(task: ObservedTask) -> dict[str, Any]:
    return {
        "task_id": task.task_id,
        "flow_id": task.flow_id,
        "agent_id": task.agent_id,
        "action_type": task.action_type,
        "status": task.status,
        "trigger": task.trigger,
        "derived_task_ids": task.derived_task_ids,
        "previous_task_id": task.previous_task_id,
        "next_task_id": task.next_task_id,
        "department_id": task.department_id,
        "payload": task.payload,
        "created_at": task.created_at,
    }
