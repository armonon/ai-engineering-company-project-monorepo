"""Thin HTTP boundary for the compiled TrackFlow LangGraph."""

from __future__ import annotations

import logging
import re
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlmodel import Session, col, select
from trackflow_agent import AgentRuntime, build_graph

from database import incidents_table, inventory_engine
from models import SKU, UserInDB
from routers.inventory import _stock_by_warehouse, _to_sku_read
from security import get_current_user

logger = logging.getLogger("trackflow.agent")
router = APIRouter(prefix="/agent", tags=["agent"])


def _read_incident(incident_id: int) -> dict[str, Any] | None:
    """Read the existing TinyDB incident repository; never mutate it."""
    document = incidents_table().get(doc_id=incident_id)
    if document is None:
        return None
    return {**document, "id": document.doc_id}


def _read_inventory(query: str) -> list[dict[str, Any]]:
    """Read live SQLModel inventory and compute stock from movements."""
    useful_terms = {
        term
        for term in re.findall(r"[a-z0-9-]+", query.lower())
        if len(term) >= 3
        and term
        not in {
            "available",
            "current",
            "have",
            "inventory",
            "many",
            "much",
            "please",
            "show",
            "stock",
            "units",
            "what",
        }
    }
    with Session(inventory_engine()) as session:
        skus = session.exec(select(SKU).order_by(col(SKU.id))).all()
        if useful_terms:
            skus = [
                sku
                for sku in skus
                if any(term in f"{sku.name} {sku.sku}".lower() for term in useful_terms)
            ]
        skus = skus[:10]
        totals = _stock_by_warehouse(session, [sku.id for sku in skus if sku.id is not None])
        return [_to_sku_read(sku, totals).model_dump(mode="json") for sku in skus]


runtime: AgentRuntime = build_graph(
    incident_reader=_read_incident,
    inventory_reader=_read_inventory,
)


class AgentQuery(BaseModel):
    question: str = Field(max_length=500)


class AgentAnswer(BaseModel):
    answer: str
    run_id: str


class TraceResponse(BaseModel):
    run_id: str
    events: list[dict[str, Any]]


@router.post("/query", response_model=AgentAnswer)
def query_agent(
    payload: AgentQuery,
    _caller: UserInDB = Depends(get_current_user),
) -> AgentAnswer:
    """Invoke the already-compiled graph; no orchestration belongs here."""
    try:
        result = runtime.invoke(payload.question)
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
    events = runtime.traces.get(run_id)
    if not events:
        raise HTTPException(status_code=404, detail="Agent trace not found.")
    return TraceResponse(run_id=run_id, events=events)
