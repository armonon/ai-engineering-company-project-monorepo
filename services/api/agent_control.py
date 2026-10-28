"""Atomic operational controls for one observed agent execution at a time."""

from __future__ import annotations

import threading
from datetime import UTC, datetime
from typing import Any, Literal

from sqlmodel import Session, select

from agent_observability import emit_event, record_task
from models import ObservedAgent, ObservedFlow, ObservedFlowAgent, ObservedTask, RfpTicket

ControlAction = Literal["pause", "resume", "cancel"]
_locks: dict[tuple[str, str], threading.Lock] = {}
_locks_guard = threading.Lock()


class InvalidControlTransition(ValueError):
    pass


def _lock_for(agent_id: str, flow_id: str) -> threading.Lock:
    key = (agent_id, flow_id)
    with _locks_guard:
        return _locks.setdefault(key, threading.Lock())


def _checkpoint_payload(
    session: Session,
    agent_id: str,
    flow_id: str,
    participation: ObservedFlowAgent,
) -> dict[str, Any]:
    latest = session.exec(
        select(ObservedTask)
        .where(
            ObservedTask.flow_id == flow_id,
            ObservedTask.agent_id == agent_id,
        )
        .order_by(ObservedTask.created_at.desc(), ObservedTask.task_id.desc())
    ).first()
    checkpoint: dict[str, Any] = {
        "last_task_id": latest.task_id if latest else None,
        "previous_status": participation.status,
        "captured_at": datetime.now(UTC).isoformat(),
    }
    if agent_id == "rfp_pipeline" and flow_id.startswith("rfp-"):
        ticket_id = flow_id.removeprefix("rfp-")
        ticket = session.get(RfpTicket, ticket_id)
        approval_states = ticket.handoff_payload.get("approval_states", {}) if ticket else {}
        checkpoint["langgraph_thread_ids"] = [
            state["thread_id"]
            for state in approval_states.values()
            if state.get("thread_id")
        ]
    else:
        checkpoint["chat_hold_open"] = True
    return checkpoint


def control_state(session: Session, agent_id: str, flow_id: str) -> dict[str, Any]:
    agent = session.get(ObservedAgent, agent_id)
    flow = session.get(ObservedFlow, flow_id)
    participation = session.exec(
        select(ObservedFlowAgent).where(
            ObservedFlowAgent.flow_id == flow_id,
            ObservedFlowAgent.agent_id == agent_id,
        )
    ).first()
    if agent is None or flow is None or participation is None:
        raise LookupError("Observed agent execution not found")
    return {
        "agent_id": agent_id,
        "flow_id": flow_id,
        "agent_status": participation.status,
        "flow_status": flow.status,
        "control_version": participation.control_version,
        "checkpoint": participation.checkpoint_data,
    }


def apply_control(
    session: Session,
    *,
    agent_id: str,
    flow_id: str,
    action: ControlAction,
    actor_id: str,
) -> dict[str, Any]:
    if action not in {"pause", "resume", "cancel"}:
        raise InvalidControlTransition("command must be pause, resume, or cancel")
    with _lock_for(agent_id, flow_id):
        agent = session.get(ObservedAgent, agent_id)
        flow = session.get(ObservedFlow, flow_id)
        participation = session.exec(
            select(ObservedFlowAgent).where(
                ObservedFlowAgent.flow_id == flow_id,
                ObservedFlowAgent.agent_id == agent_id,
            )
        ).first()
        if agent is None or flow is None or participation is None:
            raise LookupError("Observed agent execution not found")

        allowed = {
            "pause": {"running", "waiting_for_human"},
            "resume": {"paused"},
            "cancel": {"running", "paused", "waiting_for_human"},
        }
        if participation.status not in allowed[action]:
            raise InvalidControlTransition(
                f"Cannot {action} an execution in {participation.status!r} status."
            )

        previous = session.exec(
            select(ObservedTask)
            .where(
                ObservedTask.flow_id == flow_id,
                ObservedTask.agent_id == agent_id,
            )
            .order_by(ObservedTask.created_at.desc(), ObservedTask.task_id.desc())
        ).first()
        previous_id = previous.task_id if previous else None

        if action == "pause":
            participation.checkpoint_data = _checkpoint_payload(
                session, agent_id, flow_id, participation
            )
            new_status = "paused"
            participation.paused_at = datetime.now(UTC)
        elif action == "resume":
            if not participation.checkpoint_data:
                raise InvalidControlTransition("Paused execution has no resumable checkpoint.")
            new_status = str(participation.checkpoint_data.get("previous_status") or "running")
            if new_status not in {"running", "waiting_for_human"}:
                new_status = "running"
        else:
            new_status = "cancelled"
            participation.cancelled_at = datetime.now(UTC)

        control_task = record_task(
            session,
            flow_id=flow_id,
            agent_id=agent_id,
            action_type=action,
            trigger=previous_id or f"external:operator:{actor_id}",
            previous_task_id=previous_id,
            actor_id=actor_id,
            payload={
                "checkpoint_last_task_id": (
                    participation.checkpoint_data or {}
                ).get("last_task_id")
            },
        )

        if action == "cancel":
            active_tasks = session.exec(
                select(ObservedTask).where(
                    ObservedTask.flow_id == flow_id,
                    ObservedTask.agent_id == agent_id,
                    ObservedTask.status.in_(["pending", "running"]),
                )
            ).all()
            for task in active_tasks:
                task.status = "cancelled"
                session.add(task)
            flow.completed_at = datetime.now(UTC)
        participation.status = new_status
        participation.control_version += 1
        agent.current_status = new_status
        agent.needs_intervention = False
        agent.updated_at = datetime.now(UTC)
        flow.status = new_status
        session.add(participation)
        session.add(agent)
        session.add(flow)
        session.commit()

        timestamp = datetime.now(UTC).isoformat()
        event = {
            "agent_id": agent_id,
            "flow_id": flow_id,
            "action": action,
            "actor_id": actor_id,
            "timestamp": timestamp,
            "status": new_status,
            "task_id": control_task.task_id,
            "control_version": participation.control_version,
        }
        emit_event(session, "control_applied", event)
        emit_event(
            session,
            "agent_status_changed",
            {"agent_id": agent_id, "flow_id": flow_id, "status": new_status},
        )
        return event
