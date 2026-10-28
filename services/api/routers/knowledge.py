"""Authenticated TrackFlow sales knowledge endpoint."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from trackflow_pipeline.rag import query

from models import UserInDB
from security import get_current_user

logger = logging.getLogger("trackflow.knowledge")
router = APIRouter(prefix="/knowledge", tags=["knowledge"])


class KnowledgeQuery(BaseModel):
    question: str = Field(min_length=3, max_length=500)


class KnowledgeAnswer(BaseModel):
    answer: str


@router.post("/query", response_model=KnowledgeAnswer)
def answer_knowledge_question(
    payload: KnowledgeQuery,
    _caller: UserInDB = Depends(get_current_user),
) -> KnowledgeAnswer:
    """Retrieve policy evidence and return only the generated answer."""
    try:
        return KnowledgeAnswer(answer=query(payload.question.strip()))
    except Exception as exc:
        logger.exception("Knowledge pipeline unavailable", exc_info=exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="The TrackFlow knowledge service is temporarily unavailable. Please try again.",
        ) from exc
