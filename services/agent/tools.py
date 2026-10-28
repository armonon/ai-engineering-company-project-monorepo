"""Typed, read-only operational tools used by the support graph.

The readers are injected by the API package so this package never owns a
parallel copy of incident or inventory data.  A bounded executor gives every
lookup the same explicit timeout and turns service failures into typed results
the graph can route through safely.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeout
from dataclasses import dataclass
from typing import Any

TOOL_TIMEOUT_SECONDS = 4.0
_EXECUTOR = ThreadPoolExecutor(max_workers=4, thread_name_prefix="trackflow-tools")

IncidentReader = Callable[[int], Mapping[str, Any] | None]
InventoryReader = Callable[[str], Sequence[Mapping[str, Any]]]


@dataclass(frozen=True)
class TicketLookupInput:
    ticket_id: int


@dataclass(frozen=True)
class TicketLookupOutput:
    ticket_id: int
    found: bool
    status: str | None = None
    category: str | None = None
    origin: str | None = None
    branch: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
    error: str | None = None

    def as_context(self) -> dict[str, Any]:
        return {
            "source_document": "live-incident-manager",
            "section": f"incident-{self.ticket_id}",
            "text": (
                f"Incident {self.ticket_id}: status={self.status}; "
                f"category={self.category}; origin={self.origin}; "
                f"branch={self.branch}; updated_at={self.updated_at}."
            ),
        }


@dataclass(frozen=True)
class InventoryProduct:
    product_id: int
    name: str
    sku: str
    warehouse: str
    current_stock: int


@dataclass(frozen=True)
class InventoryLookupInput:
    query: str


@dataclass(frozen=True)
class InventoryLookupOutput:
    query: str
    products: tuple[InventoryProduct, ...] = ()
    error: str | None = None

    def as_context(self) -> list[dict[str, Any]]:
        return [
            {
                "source_document": "live-inventory-manager",
                "section": product.sku,
                "text": (
                    f"{product.name} ({product.sku}) has {product.current_stock} "
                    f"units in warehouse {product.warehouse}."
                ),
            }
            for product in self.products
        ]


def lookup_ticket(
    request: TicketLookupInput,
    reader: IncidentReader | None,
    timeout_seconds: float = TOOL_TIMEOUT_SECONDS,
) -> TicketLookupOutput:
    """Read one real incident with a hard timeout and honest failure result."""
    if reader is None:
        return TicketLookupOutput(
            ticket_id=request.ticket_id,
            found=False,
            error="incident_service_unavailable",
        )
    future = _EXECUTOR.submit(reader, request.ticket_id)
    try:
        record = future.result(timeout=timeout_seconds)
    except FutureTimeout:
        future.cancel()
        return TicketLookupOutput(ticket_id=request.ticket_id, found=False, error="timeout")
    except Exception:
        return TicketLookupOutput(
            ticket_id=request.ticket_id,
            found=False,
            error="incident_service_unavailable",
        )
    if record is None:
        return TicketLookupOutput(ticket_id=request.ticket_id, found=False, error="not_found")
    return TicketLookupOutput(
        ticket_id=request.ticket_id,
        found=True,
        status=str(record.get("status") or "unknown"),
        category=str(record.get("category") or "unknown"),
        origin=str(record.get("origin") or "unknown"),
        branch=str(record.get("branch") or "unknown"),
        created_at=str(record.get("created_at") or "unknown"),
        updated_at=str(record.get("updated_at") or "unknown"),
    )


def lookup_inventory(
    request: InventoryLookupInput,
    reader: InventoryReader | None,
    timeout_seconds: float = TOOL_TIMEOUT_SECONDS,
) -> InventoryLookupOutput:
    """Search the real inventory manager without ever mutating stock."""
    if reader is None:
        return InventoryLookupOutput(query=request.query, error="inventory_service_unavailable")
    future = _EXECUTOR.submit(reader, request.query)
    try:
        records = future.result(timeout=timeout_seconds)
    except FutureTimeout:
        future.cancel()
        return InventoryLookupOutput(query=request.query, error="timeout")
    except Exception:
        return InventoryLookupOutput(query=request.query, error="inventory_service_unavailable")

    products = tuple(
        InventoryProduct(
            product_id=int(record["id"]),
            name=str(record["name"]),
            sku=str(record["sku"]),
            warehouse=str(record["warehouse"]),
            current_stock=int(record["current_stock"]),
        )
        for record in records
    )
    return InventoryLookupOutput(
        query=request.query,
        products=products,
        error=None if products else "not_found",
    )
