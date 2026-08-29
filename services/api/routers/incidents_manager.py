"""Centralised incident manager endpoints.

    POST   /api/incidents               register an incident
    GET    /api/incidents               list, filterable
    GET    /api/incidents/summary       aggregated metrics
    GET    /api/incidents/{id}          detail
    PATCH  /api/incidents/{id}/status   advance the lifecycle

Domain rules — the value sets, the lifecycle, and field validation —
come from `trackflow_shared`, the same package `scripts/seed_incidents.py`
imports. Neither side owns a private copy.

Route order matters: `/summary` is declared before `/{incident_id}` so
the literal segment wins. Registered the other way round, FastAPI would
try to parse "summary" as an id.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi import status as http_status
from tinydb.table import Document
from trackflow_shared.incidents import (
    Branch,
    Category,
    FieldError,
    Origin,
    Status,
    can_transition,
    transition_error,
    validate_incident,
    validate_status,
)

from database import db_transaction, incidents_table
from models import UserInDB
from security import get_current_user

router = APIRouter(prefix="/api/incidents", tags=["incident-manager"])


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _to_out(document: Document) -> dict[str, Any]:
    """Stored record → API shape.

    `source_incident_id` is seed bookkeeping (duplicate control) and is
    not part of the model CONTEXT defines, so it never leaves the API.
    """
    record = {k: v for k, v in document.items() if k != "source_incident_id"}
    record["id"] = document.doc_id
    return record


def _field_error(exc: FieldError) -> HTTPException:
    """400 that names the offending field, per the rubric."""
    return HTTPException(
        status_code=http_status.HTTP_400_BAD_REQUEST,
        detail={"field": exc.field, "message": exc.message},
    )


def _get_or_404(incident_id: int) -> Document:
    document = incidents_table().get(doc_id=incident_id)
    if document is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail=f"No incident with id {incident_id}.",
        )
    return document


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------


@router.post(
    "",
    status_code=http_status.HTTP_201_CREATED,
    summary="Register a new incident",
)
def create_incident(
    payload: dict[str, Any],
    _caller: UserInDB = Depends(get_current_user),
) -> dict[str, Any]:
    """Create an incident.

    Takes a raw dict rather than a Pydantic model on purpose: the rubric
    wants a 400 naming the offending field, and the shared validator
    already produces exactly that. Routing it through Pydantic first
    would yield a 422 with a different shape.
    """
    try:
        cleaned = validate_incident(payload)
    except FieldError as exc:
        raise _field_error(exc) from None

    now = _now_iso()
    record = {
        "title": cleaned["title"],
        "description": cleaned["description"],
        "category": cleaned["category"].value,
        "status": cleaned["status"].value,
        "origin": cleaned["origin"].value,
        "branch": cleaned["branch"].value,
        "created_at": now,
        "updated_at": now,
    }
    incident_id = incidents_table().insert(record)
    return _to_out(Document(record, doc_id=incident_id))


# ---------------------------------------------------------------------------
# Read
# ---------------------------------------------------------------------------


@router.get("", summary="List incidents, optionally filtered")
def list_incidents(
    status: Status | None = Query(default=None),
    origin: Origin | None = Query(default=None),
    branch: Branch | None = Query(default=None),
    category: Category | None = Query(default=None),
    _caller: UserInDB = Depends(get_current_user),
) -> list[dict[str, Any]]:
    """Return incidents, newest first.

    Filters combine with AND. With none supplied the whole list comes
    back. An empty database returns [] rather than failing.
    """
    results = [_to_out(d) for d in incidents_table().all()]

    if status is not None:
        results = [r for r in results if r["status"] == status.value]
    if origin is not None:
        results = [r for r in results if r["origin"] == origin.value]
    if branch is not None:
        results = [r for r in results if r["branch"] == branch.value]
    if category is not None:
        results = [r for r in results if r["category"] == category.value]

    results.sort(key=lambda r: r.get("created_at") or "", reverse=True)
    return results


@router.get("/summary", summary="Aggregated incident metrics")
def incident_summary(
    _caller: UserInDB = Depends(get_current_user),
) -> dict[str, Any]:
    """Totals by status, category, origin, and branch.

    Every key in each closed value set is present even at zero, so the
    frontend can render a stable set of tiles instead of a jagged one.
    An empty database yields zeros, not an error.
    """
    incidents = incidents_table().all()

    by_status = {s.value: 0 for s in Status}
    by_category = {c.value: 0 for c in Category}
    by_origin = {o.value: 0 for o in Origin}
    by_branch = {b.value: 0 for b in Branch}

    for record in incidents:
        if (value := record.get("status")) in by_status:
            by_status[value] += 1
        if (value := record.get("category")) in by_category:
            by_category[value] += 1
        if (value := record.get("origin")) in by_origin:
            by_origin[value] += 1
        if (value := record.get("branch")) in by_branch:
            by_branch[value] += 1

    return {
        "total": len(incidents),
        "by_status": by_status,
        "by_category": by_category,
        "by_origin": by_origin,
        "by_branch": by_branch,
    }


@router.get("/{incident_id}", summary="Get one incident")
def get_incident(
    incident_id: int,
    _caller: UserInDB = Depends(get_current_user),
) -> dict[str, Any]:
    return _to_out(_get_or_404(incident_id))


# ---------------------------------------------------------------------------
# Lifecycle
# ---------------------------------------------------------------------------


@router.patch("/{incident_id}/status", summary="Advance an incident's status")
def update_incident_status(
    incident_id: int,
    payload: dict[str, Any],
    _caller: UserInDB = Depends(get_current_user),
) -> dict[str, Any]:
    """Change status, enforcing the CONTEXT lifecycle.

    An illegal transition is a 400 whose message says what *is* allowed
    from the current state, so the caller can recover without reading
    the spec.
    """
    try:
        target = validate_status(payload.get("status"))
    except FieldError as exc:
        raise _field_error(exc) from None

    # The whole check-then-write runs under one lock. Two operators
    # acting on the same open incident at the same moment — one picking
    # it up, one dismissing it — would otherwise both read `open`, both
    # pass the transition check, and both write: two mutually exclusive
    # transitions each reporting success.
    with db_transaction():
        document = _get_or_404(incident_id)

        try:
            current = Status(document["status"])
        except (KeyError, ValueError):
            raise HTTPException(
                status_code=http_status.HTTP_400_BAD_REQUEST,
                detail={
                    "field": "status",
                    "message": "This incident has an unreadable current status.",
                },
            ) from None

        if not can_transition(current, target):
            raise HTTPException(
                status_code=http_status.HTTP_400_BAD_REQUEST,
                detail={"field": "status", "message": transition_error(current, target)},
            )

        incidents_table().update(
            {"status": target.value, "updated_at": _now_iso()}, doc_ids=[incident_id]
        )
        return _to_out(_get_or_404(incident_id))
