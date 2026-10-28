"""Authenticated read-only observability API and resumable SSE stream."""

from __future__ import annotations

import asyncio
import json
import queue
from collections.abc import AsyncIterator
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import func
from sqlmodel import Session, select

from agent_observability import (
    available_actions,
    ensure_registered_agents,
    refresh_intervention_flags,
    serialize_task,
    subscribe,
)
from database import get_db
from models import (
    ObservabilityEvent,
    ObservedAgent,
    ObservedFlow,
    ObservedFlowAgent,
    ObservedTask,
    UserInDB,
)
from security import get_current_user

router = APIRouter(prefix="/observability", tags=["agent-observability"])


def _agent_payload(agent: ObservedAgent) -> dict[str, Any]:
    return {
        "agent_id": agent.agent_id,
        "name": agent.name,
        "agent_type": agent.agent_type,
        "owner_area": agent.owner_area,
        "flow_types": agent.flow_types,
        "status": agent.current_status,
        "needs_intervention": agent.needs_intervention,
        "available_actions": available_actions(
            agent.current_status, agent.needs_intervention
        ),
        "updated_at": agent.updated_at,
    }


def _flow_payload(session: Session, flow: ObservedFlow) -> dict[str, Any]:
    participations = session.exec(
        select(ObservedFlowAgent).where(ObservedFlowAgent.flow_id == flow.flow_id)
    ).all()
    participants: list[dict[str, Any]] = []
    for participation in participations:
        agent = session.get(ObservedAgent, participation.agent_id)
        tasks = session.exec(
            select(ObservedTask)
            .where(
                ObservedTask.flow_id == flow.flow_id,
                ObservedTask.agent_id == participation.agent_id,
            )
            .order_by(ObservedTask.created_at, ObservedTask.task_id)
        ).all()
        participants.append(
            {
                "agent_id": participation.agent_id,
                "agent_name": agent.name if agent else participation.agent_id,
                "status": participation.status,
                "tasks": [serialize_task(task) for task in tasks],
            }
        )
    return {
        "flow_id": flow.flow_id,
        "flow_type": flow.flow_type,
        "status": flow.status,
        "triggered_by": flow.triggered_by,
        "started_at": flow.started_at,
        "completed_at": flow.completed_at,
        "participating_agents": participants,
    }


@router.get("/agents")
def list_agents(
    _caller: UserInDB = Depends(get_current_user),
    session: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    ensure_registered_agents(session)
    refresh_intervention_flags(session)
    agents = session.exec(select(ObservedAgent).order_by(ObservedAgent.agent_id)).all()
    return [_agent_payload(agent) for agent in agents]


@router.get("/agents/{agent_id}")
def agent_detail(
    agent_id: str,
    _caller: UserInDB = Depends(get_current_user),
    session: Session = Depends(get_db),
) -> dict[str, Any]:
    ensure_registered_agents(session)
    refresh_intervention_flags(session)
    agent = session.get(ObservedAgent, agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail="Observed agent not found.")
    participations = session.exec(
        select(ObservedFlowAgent)
        .where(ObservedFlowAgent.agent_id == agent_id)
        .order_by(ObservedFlowAgent.id.desc())
        .limit(5)
    ).all()
    last_flows = []
    for participation in participations:
        flow = session.get(ObservedFlow, participation.flow_id)
        if flow is None:
            continue
        tasks = session.exec(
            select(ObservedTask)
            .where(
                ObservedTask.agent_id == agent_id,
                ObservedTask.flow_id == flow.flow_id,
            )
            .order_by(ObservedTask.created_at, ObservedTask.task_id)
        ).all()
        last_flows.append(
            {
                "flow_id": flow.flow_id,
                "flow_type": flow.flow_type,
                "status": participation.status,
                "triggered_by": flow.triggered_by,
                "tasks": [serialize_task(task) for task in tasks],
            }
        )
    quick_log = session.exec(
        select(ObservedTask)
        .where(ObservedTask.agent_id == agent_id)
        .order_by(ObservedTask.created_at.desc(), ObservedTask.task_id.desc())
        .limit(10)
    ).all()
    return {
        **_agent_payload(agent),
        "last_5_flows": last_flows,
        "last_10_tasks": [serialize_task(task) for task in quick_log],
    }


@router.get("/executions")
def execution_log(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    agent_id: str | None = None,
    flow_id: str | None = None,
    _caller: UserInDB = Depends(get_current_user),
    session: Session = Depends(get_db),
) -> dict[str, Any]:
    conditions = []
    if agent_id:
        conditions.append(ObservedTask.agent_id == agent_id)
    if flow_id:
        conditions.append(ObservedTask.flow_id == flow_id)
    statement = select(ObservedTask)
    count_statement = select(func.count()).select_from(ObservedTask)
    for condition in conditions:
        statement = statement.where(condition)
        count_statement = count_statement.where(condition)
    tasks = session.exec(
        statement.order_by(ObservedTask.created_at.desc(), ObservedTask.task_id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    total = int(session.exec(count_statement).one())
    return {
        "page": page,
        "page_size": page_size,
        "total": total,
        "items": [serialize_task(task) for task in tasks],
    }


@router.get("/tasks/{task_id}")
def task_trace(
    task_id: str,
    _caller: UserInDB = Depends(get_current_user),
    session: Session = Depends(get_db),
) -> dict[str, Any]:
    task = session.get(ObservedTask, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Observed task not found.")
    previous = session.get(ObservedTask, task.previous_task_id) if task.previous_task_id else None
    following = session.get(ObservedTask, task.next_task_id) if task.next_task_id else None
    derived = [session.get(ObservedTask, derived_id) for derived_id in task.derived_task_ids]
    return {
        **serialize_task(task),
        "previous_task": serialize_task(previous) if previous else None,
        "next_task": serialize_task(following) if following else None,
        "derived_tasks": [serialize_task(item) for item in derived if item],
    }


@router.get("/flows")
def list_flows(
    _caller: UserInDB = Depends(get_current_user),
    session: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    flows = session.exec(select(ObservedFlow).order_by(ObservedFlow.started_at.desc())).all()
    return [_flow_payload(session, flow) for flow in flows]


@router.get("/flows/{flow_id}")
def flow_detail(
    flow_id: str,
    _caller: UserInDB = Depends(get_current_user),
    session: Session = Depends(get_db),
) -> dict[str, Any]:
    flow = session.get(ObservedFlow, flow_id)
    if flow is None:
        raise HTTPException(status_code=404, detail="Observed flow not found.")
    return _flow_payload(session, flow)


def _format_sse(event: dict[str, Any]) -> str:
    return (
        f"id: {event['id']}\n"
        f"event: {event['event']}\n"
        f"data: {json.dumps(event['data'], separators=(',', ':'))}\n\n"
    )


@router.get("/stream")
def stream_events(
    last_event_id_header: str | None = Header(default=None, alias="Last-Event-ID"),
    last_event_id: int | None = Query(default=None, ge=0),
    max_events: int | None = Query(default=None, ge=1, le=100),
    _caller: UserInDB = Depends(get_current_user),
    session: Session = Depends(get_db),
) -> StreamingResponse:
    try:
        cursor = last_event_id if last_event_id is not None else int(last_event_id_header or 0)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Last-Event-ID must be an integer.") from exc

    async def events() -> AsyncIterator[str]:
        sent = 0
        replay = session.exec(
            select(ObservabilityEvent)
            .where(ObservabilityEvent.id > cursor)
            .order_by(ObservabilityEvent.id)
        ).all()
        for event in replay:
            yield _format_sse(
                {"id": event.id, "event": event.event_name, "data": event.data}
            )
            sent += 1
            if max_events and sent >= max_events:
                return
        with subscribe() as subscriber:
            while True:
                try:
                    event = await asyncio.to_thread(subscriber.get, True, 15)
                    yield _format_sse(event)
                    sent += 1
                    if max_events and sent >= max_events:
                        return
                except queue.Empty:
                    yield ": keep-alive\n\n"

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
