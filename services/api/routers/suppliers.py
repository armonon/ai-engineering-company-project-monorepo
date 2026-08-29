"""Supplier directory endpoints.

Six routes, all backed by TinyDB:

    POST   /suppliers                 register a supplier
    GET    /suppliers                 list, optionally filtered
    GET    /suppliers/{id}            detail
    PATCH  /suppliers/{id}/rate       update rate + stamp updated_at
    PATCH  /suppliers/{id}/status     activate / suspend
    DELETE /suppliers/{id}            remove

Validation lives in models.py, so an invalid status or a non-positive
rate is rejected by Pydantic with 422 before it ever touches the
database — which is exactly what the tech lead asked for.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi import status as http_status
from tinydb.table import Document

from database import suppliers_table
from models import (
    Category,
    Country,
    DeleteResponse,
    RateUpdate,
    Status,
    StatusUpdate,
    SupplierCreate,
    SupplierOut,
    UserInDB,
    utcnow,
)
from security import get_current_user

router = APIRouter(prefix="/suppliers", tags=["suppliers"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _to_out(document: Document) -> SupplierOut:
    """TinyDB Document -> SupplierOut, folding the doc_id in as `id`."""
    return SupplierOut(**{**document, "id": document.doc_id})


def _get_or_404(supplier_id: int) -> Document:
    document = suppliers_table().get(doc_id=supplier_id)
    if document is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail=f"No supplier with id {supplier_id}.",
        )
    return document


def _storable(payload: SupplierCreate) -> dict[str, Any]:
    """JSON-safe dict for TinyDB: enums become their values, datetimes
    become ISO strings. TinyDB writes plain JSON and cannot serialise
    Python objects."""
    record = payload.model_dump(mode="json")
    record["updated_at"] = utcnow().isoformat()
    return record


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.post(
    "",
    response_model=SupplierOut,
    status_code=http_status.HTTP_201_CREATED,
    summary="Register a new supplier",
)
def create_supplier(
    payload: SupplierCreate,
    _caller: UserInDB = Depends(get_current_user),
) -> SupplierOut:
    """Create a supplier and return it with its TinyDB-assigned id.

    Invalid input (bad status, bad category, rate <= 0, currency that
    disagrees with the country) is rejected with 422 by the model.
    """
    table = suppliers_table()
    record = _storable(payload)
    supplier_id = table.insert(record)
    return _to_out(Document(record, doc_id=supplier_id))


@router.get(
    "",
    response_model=list[SupplierOut],
    summary="List suppliers, optionally filtered by country and/or category",
)
def list_suppliers(
    country: Country | None = Query(
        default=None, description="Filter to a single contract country."
    ),
    category: Category | None = Query(
        default=None,
        description="Filter to suppliers that provide this category.",
    ),
    supplier_status: Status | None = Query(
        default=None,
        alias="status",
        description="Optional extra filter by status.",
    ),
    # The directory holds negotiated rates and supplier contacts. Every
    # write here was protected; both reads were not, which left the
    # commercial data readable by anyone who could reach the API.
    _caller: UserInDB = Depends(get_current_user),
) -> list[SupplierOut]:
    """Return every supplier, narrowed by whatever filters were given.

    With no query parameters this returns the whole directory.
    Filters combine with AND, so `?country=Spain&category=carrier_last_mile`
    answers "what last-mile carriers do we have in Spain?".
    """
    results = [_to_out(doc) for doc in suppliers_table().all()]

    if country is not None:
        results = [s for s in results if s.country == country]
    if category is not None:
        # `categories` is a list — match if the requested one is present.
        results = [s for s in results if category in s.categories]
    if supplier_status is not None:
        results = [s for s in results if s.status == supplier_status]

    return results


@router.get(
    "/{supplier_id}",
    response_model=SupplierOut,
    summary="Get one supplier by id",
)
def get_supplier(
    supplier_id: int,
    _caller: UserInDB = Depends(get_current_user),
) -> SupplierOut:
    return _to_out(_get_or_404(supplier_id))


@router.patch(
    "/{supplier_id}/rate",
    response_model=SupplierOut,
    summary="Update a supplier's rate and stamp updated_at",
)
def update_rate(
    supplier_id: int,
    payload: RateUpdate,
    _caller: UserInDB = Depends(get_current_user),
) -> SupplierOut:
    """Update `rate_per_shipment` and record when it changed.

    CONTEXT § Business constraints: "Every update to rate_per_shipment
    must automatically record updated_at." Carlos audits cost evolution
    from this timestamp, so it is written on every rate change without
    the client having to ask.
    """
    _get_or_404(supplier_id)
    changes = {
        "rate_per_shipment": payload.rate_per_shipment,
        "updated_at": utcnow().isoformat(),
    }
    suppliers_table().update(changes, doc_ids=[supplier_id])
    return _to_out(_get_or_404(supplier_id))


@router.patch(
    "/{supplier_id}/status",
    response_model=SupplierOut,
    summary="Activate or suspend a supplier",
)
def update_status(
    supplier_id: int,
    payload: StatusUpdate,
    _caller: UserInDB = Depends(get_current_user),
) -> SupplierOut:
    """Flip a supplier between active and suspended.

    Anything outside the two CONTEXT statuses is rejected with 422 by
    the StatusUpdate model before reaching this body.
    """
    _get_or_404(supplier_id)
    suppliers_table().update(
        {"status": payload.status.value}, doc_ids=[supplier_id]
    )
    return _to_out(_get_or_404(supplier_id))


@router.delete(
    "/{supplier_id}",
    response_model=DeleteResponse,
    summary="Remove a supplier from the directory",
)
def delete_supplier(
    supplier_id: int,
    _caller: UserInDB = Depends(get_current_user),
) -> DeleteResponse:
    """Delete a supplier.

    Note for operators: TrackFlow's usual workflow is to *suspend*
    a supplier with a high incident rate rather than delete it, because
    the suspension history is operationally relevant. Use
    PATCH /suppliers/{id}/status unless the record is genuinely bogus.
    """
    document = _get_or_404(supplier_id)
    name = document.get("name", "")
    suppliers_table().remove(doc_ids=[supplier_id])
    return DeleteResponse(
        id=supplier_id,
        deleted=True,
        message=f"Supplier '{name}' (id {supplier_id}) removed from the directory.",
    )
