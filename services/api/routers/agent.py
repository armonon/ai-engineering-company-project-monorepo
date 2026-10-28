"""Thin HTTP boundary for the compiled TrackFlow LangGraph."""

from __future__ import annotations

import json
import logging
import os
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlmodel import Session
from trackflow_agent import AgentRuntime, CompanyToolsMCPClient, MemoryStore, build_graph

from agent_observability import change_status, record_task, start_flow
from database import inventory_engine
from models import UserInDB
from security import get_current_user

logger = logging.getLogger("trackflow.agent")
router = APIRouter(prefix="/agent", tags=["agent"])


company_tools = CompanyToolsMCPClient.from_env()
memory_store = MemoryStore()


def authorize_ticket(principal: str, ticket_id: int) -> bool:
    """Deny by default; admins or an explicit per-user allowlist may read."""
    role, _, user_id = principal.partition(":")
    if role == "admin":
        return True
    try:
        configured = json.loads(os.getenv("AGENT_TICKET_ACCESS_JSON", "{}"))
        allowed = configured.get(user_id, [])
        return ticket_id in {int(value) for value in allowed}
    except (AttributeError, TypeError, ValueError, json.JSONDecodeError):
        logger.warning("Invalid AGENT_TICKET_ACCESS_JSON; denying ticket access")
        return False


runtime: AgentRuntime = build_graph(
    incident_reader=company_tools.get_incident,
    inventory_reader=company_tools.query_inventory,
    memory_store=memory_store,
    ticket_authorizer=authorize_ticket,
)


class AgentQuery(BaseModel):
    question: str = Field(max_length=500)


class AgentAnswer(BaseModel):
    answer: str
    run_id: str


class TraceResponse(BaseModel):
    run_id: str
    events: list[dict[str, Any]]


@router.get("/guardrails/summary")
def guardrail_summary(
    _caller: UserInDB = Depends(get_current_user),
) -> dict[str, dict[str, int] | int]:
    return runtime.traces.guardrail_summary()


@router.post("/query", response_model=AgentAnswer)
def query_agent(
    payload: AgentQuery,
    _caller: UserInDB = Depends(get_current_user),
) -> AgentAnswer:
    """Invoke the already-compiled graph; no orchestration belongs here."""
    try:
        principal = f"{_caller.role.value}:{_caller.id}"
        result = runtime.invoke(payload.question, user_id=principal)
        try:
            with Session(inventory_engine()) as observation_session:
                flow_id = f"chat-{result.run_id}"
                start_flow(
                    observation_session,
                    flow_id=flow_id,
                    flow_type="chat_session",
                    triggered_by=f"client_inbound_message:{result.run_id}",
                    agent_ids=["first_line_cx"],
                )
                query_task = record_task(
                    observation_session,
                    flow_id=flow_id,
                    agent_id="first_line_cx",
                    action_type="query",
                    trigger=f"external:client_inbound_message:{result.run_id}",
                    payload={"run_id": result.run_id},
                )
                record_task(
                    observation_session,
                    flow_id=flow_id,
                    agent_id="first_line_cx",
                    action_type="deliver",
                    trigger=query_task.task_id,
                    previous_task_id=query_task.task_id,
                    payload={"run_id": result.run_id},
                )
                change_status(
                    observation_session,
                    flow_id=flow_id,
                    agent_id="first_line_cx",
                    status="completed",
                )
        except Exception:
            logger.exception("Could not persist first-line CX observability events")
        return AgentAnswer(answer=result.answer, run_id=result.run_id)
    except Exception as exc:
        logger.exception("Agent graph failed", exc_info=exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="The TrackFlow support agent is temporarily unavailable. Please try again.",
        ) from exc


@router.get("/traces/{run_id}", response_model=TraceResponse)
def read_agent_trace(
    run_id: str,
    _caller: UserInDB = Depends(get_current_user),
) -> TraceResponse:
    principal = f"{_caller.role.value}:{_caller.id}"
    if _caller.role.value != "admin" and not runtime.traces.is_owner(run_id, principal):
        raise HTTPException(status_code=404, detail="Agent trace not found.")
    events = runtime.traces.get(run_id)
    if not events:
        raise HTTPException(status_code=404, detail="Agent trace not found.")
    return TraceResponse(run_id=run_id, events=events)
