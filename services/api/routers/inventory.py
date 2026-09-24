"""Inventory API — SKUs and stock movements, backed by Supabase.

    GET    /inventory/products          list SKUs with computed stock
    POST   /inventory/products          register a SKU
    GET    /inventory/products/{id}     one SKU with its stock
    POST   /inventory/orders/inbound    register a goods receipt
    POST   /inventory/orders/outbound   register a dispatch or a loss
    GET    /inventory/orders            the unified movement feed

Two databases meet in this file and are used for different things:

  * `Depends(get_current_user)` reads the caller from **TinyDB**. Its id
    becomes `user_uuid` on every movement written.
  * `Depends(get_db)` yields a **Supabase** SQLModel session, one per
    request. There is no module-level session.

Every route is authenticated. CONTEXT is explicit that reads are not
public here — a SKU row names the client brand and its stock position,
which is commercially sensitive between the brands TrackFlow serves.

The rule the whole module exists to enforce: stock is never stored. It
is `SUM(entries) - SUM(exits)`, computed per SKU **per warehouse**, and
no endpoint accepts a stock value.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlmodel import Session, col, func, select

from database import get_db
from inventory_telemetry_config import minimum_stock_for_sku, telemetry_client_id
from models import SKU, StockEntry, StockExit, UserInDB, Warehouse
from routers.telemetry import record_stub_batch
from schemas import (
    DirectStockEditAttempt,
    InventoryAuditCreate,
    InventoryAuditRead,
    MovementRead,
    SKUCreate,
    SKURead,
    SKUSummary,
    StockEntryCreate,
    StockEntryRead,
    StockExitCreate,
    StockExitRead,
    TelemetryBatch,
    TelemetryEvent,
)
from security import get_current_user, pseudonymous_user_id

router = APIRouter(prefix="/inventory", tags=["inventory"])


# ---------------------------------------------------------------------------
# Stock computation
# ---------------------------------------------------------------------------


def _stock_by_warehouse(session: Session, sku_ids: list[int]) -> dict[tuple[int, str], int]:
    """Net stock for every (sku_id, warehouse) pair, in two queries.

    Two aggregate queries for the whole page rather than one pair per
    SKU. Computing this inside a loop is the N+1 problem in its most
    expensive form — a hundred SKUs would mean two hundred round trips
    to Supabase, and it degrades silently as the catalogue grows.

    Returns a dict keyed by (sku_id, warehouse). A pair with no
    movements is simply absent, and callers read it as zero.
    """
    if not sku_ids:
        return {}

    totals: dict[tuple[int, str], int] = {}

    entry_rows = session.exec(
        select(
            StockEntry.sku_id,
            StockEntry.warehouse,
            func.coalesce(func.sum(col(StockEntry.quantity)), 0),
        )
        .where(col(StockEntry.sku_id).in_(sku_ids))
        .group_by(col(StockEntry.sku_id), col(StockEntry.warehouse))
    ).all()
    for sku_id, warehouse, quantity in entry_rows:
        key = (sku_id, _warehouse_value(warehouse))
        totals[key] = totals.get(key, 0) + int(quantity or 0)

    exit_rows = session.exec(
        select(
            StockExit.sku_id,
            StockExit.warehouse,
            func.coalesce(func.sum(col(StockExit.quantity)), 0),
        )
        .where(col(StockExit.sku_id).in_(sku_ids))
        .group_by(col(StockExit.sku_id), col(StockExit.warehouse))
    ).all()
    for sku_id, warehouse, quantity in exit_rows:
        key = (sku_id, _warehouse_value(warehouse))
        totals[key] = totals.get(key, 0) - int(quantity or 0)

    return totals


def _warehouse_value(warehouse: Warehouse | str) -> str:
    return warehouse.value if isinstance(warehouse, Warehouse) else str(warehouse)


def _available_stock(session: Session, sku_id: int, warehouse: Warehouse) -> int:
    """Stock for one SKU in one warehouse — the figure an exit is checked against."""
    totals = _stock_by_warehouse(session, [sku_id])
    return totals.get((sku_id, _warehouse_value(warehouse)), 0)


def _to_sku_read(sku: SKU, totals: dict[tuple[int, str], int]) -> SKURead:
    """Attach computed stock to a SKU row.

    `current_stock` is the figure for this SKU's own warehouse, which is
    what CONTEXT rule 6 means by per-warehouse: the white sneaker holds
    separate figures in LA and Zaragoza and they are never summed.

    `stock_by_warehouse` exposes the full breakdown so the scoping is
    visible in the response rather than something a reader has to infer.
    """
    assert sku.id is not None
    breakdown = {
        warehouse: total
        for (sku_id, warehouse), total in totals.items()
        if sku_id == sku.id
    }
    return SKURead(
        id=sku.id,
        name=sku.name,
        sku=sku.sku,
        client_name=sku.client_name,
        client_id=telemetry_client_id(sku.client_name),
        category=sku.category,
        warehouse=sku.warehouse,
        current_stock=breakdown.get(_warehouse_value(sku.warehouse), 0),
        stock_by_warehouse=breakdown,
        minimum_stock=minimum_stock_for_sku(sku.sku),
    )


def _lock_sku_or_404(session: Session, sku_id: int) -> SKU:
    """Fetch a SKU and hold a row lock on it for the rest of the transaction.

    This is what makes the stock check trustworthy. Without it the check
    and the insert are separable: two dispatches for the same SKU both
    read 20 units available, both pass, and both commit — shipping 30
    units that do not exist. Measured before this lock: 7 of 8 concurrent
    pairs oversold, leaving stock at -10.

    `SELECT ... FOR UPDATE` makes the second request wait until the first
    commits, so it re-reads the reduced figure and is correctly rejected.
    A row lock rather than an application lock because the API may run as
    more than one process, and a lock inside one of them would not be
    seen by the others.

    SQLite has no FOR UPDATE and serialises writers itself, so the clause
    is only emitted on backends that support it.
    """
    query = select(SKU).where(SKU.id == sku_id)
    if session.get_bind().dialect.name != "sqlite":
        query = query.with_for_update()

    sku = session.exec(query).first()
    if sku is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No SKU with id {sku_id}.",
        )
    return sku


def _get_sku_or_404(session: Session, sku_id: int) -> SKU:
    sku = session.get(SKU, sku_id)
    if sku is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No SKU with id {sku_id}.",
        )
    return sku


# ---------------------------------------------------------------------------
# SKUs
# ---------------------------------------------------------------------------


@router.get("/products", response_model=list[SKURead], summary="List SKUs with stock")
def list_products(
    warehouse: Warehouse | None = Query(
        default=None, description="Filter to one warehouse: 'LA' or 'ZGZ'."
    ),
    session: Session = Depends(get_db),
    _caller: UserInDB = Depends(get_current_user),
) -> list[SKURead]:
    skus = session.exec(select(SKU).order_by(col(SKU.id))).all()
    if warehouse is not None:
        skus = [s for s in skus if s.warehouse == warehouse]

    # One aggregate pass for the whole page, not one per SKU.
    totals = _stock_by_warehouse(session, [s.id for s in skus if s.id is not None])
    return [_to_sku_read(s, totals) for s in skus]


@router.post(
    "/products",
    response_model=SKURead,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new SKU",
)
def create_product(
    payload: SKUCreate,
    session: Session = Depends(get_db),
    _caller: UserInDB = Depends(get_current_user),
) -> SKURead:
    """Create a SKU. It starts at zero stock, necessarily.

    There is no stock field to set: the only way stock moves is a
    StockEntry, which is exactly the constraint the operations team put
    in the brief.
    """
    existing = session.exec(select(SKU).where(SKU.sku == payload.sku)).first()
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"A SKU with code '{payload.sku}' already exists.",
        )

    sku = SKU(
        name=payload.name,
        sku=payload.sku,
        client_name=payload.client_name,
        category=payload.category,
        warehouse=payload.warehouse,
    )
    session.add(sku)
    session.commit()
    session.refresh(sku)

    return _to_sku_read(sku, {})


@router.get(
    "/products/{sku_id}", response_model=SKURead, summary="Get one SKU with its stock"
)
def get_product(
    sku_id: int,
    session: Session = Depends(get_db),
    _caller: UserInDB = Depends(get_current_user),
) -> SKURead:
    sku = _get_sku_or_404(session, sku_id)
    return _to_sku_read(sku, _stock_by_warehouse(session, [sku_id]))


@router.patch(
    "/products/{sku_id}",
    status_code=status.HTTP_400_BAD_REQUEST,
    summary="Reject forbidden direct stock mutation",
)
def reject_direct_stock_edit(
    sku_id: int,
    payload: DirectStockEditAttempt,
    request: Request,
    session: Session = Depends(get_db),
    caller: UserInDB = Depends(get_current_user),
) -> None:
    """Enforce and instrument the derived-stock invariant at the API boundary."""
    sku = _get_sku_or_404(session, sku_id)
    client_id = telemetry_client_id(sku.client_name)
    if client_id is not None:
        record_stub_batch(
            TelemetryBatch(
                events=[
                    TelemetryEvent(
                        eventId=uuid4(),
                        timestamp=datetime.now(UTC),
                        sessionId=(
                            request.headers.get("x-telemetry-session-id")
                            or f"svc_{uuid4()}"
                        ),
                        userId=pseudonymous_user_id(caller.id),
                        event_type="direct_stock_edit_rejected",
                        schemaVersion="1.0.0",
                        requestId=(
                            request.headers.get("x-request-id") or f"req_{uuid4()}"
                        ),
                        properties={
                            "warehouse": (
                                "los_angeles"
                                if sku.warehouse is Warehouse.LA
                                else "zaragoza"
                            ),
                            "client_id": client_id,
                            "product_id": sku.sku,
                            "product_category": sku.category.value,
                            "quantity": payload.quantity,
                            "attempted_operation": payload.attempted_operation,
                            "endpoint_template": "/inventory/products/{id}",
                            "reason_code": "stock_is_derived",
                        },
                    )
                ]
            )
        )

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=(
            "Stock is derived from inbound and outbound orders and cannot be "
            "modified directly."
        ),
    )


@router.post(
    "/audits/check",
    response_model=InventoryAuditRead,
    summary="Compare a physical count with computed stock without modifying it",
)
def check_inventory_audit(
    payload: InventoryAuditCreate,
    session: Session = Depends(get_db),
    _caller: UserInDB = Depends(get_current_user),
) -> InventoryAuditRead:
    """Return a traceable comparison; stock remains derived from movements."""
    sku = _get_sku_or_404(session, payload.sku_id)
    if sku.warehouse != payload.warehouse:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"SKU '{sku.sku}' belongs to {sku.warehouse.value}; "
                f"it cannot be audited as {payload.warehouse.value}."
            ),
        )

    client_id = telemetry_client_id(sku.client_name)
    if client_id is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This SKU's client has no governed telemetry identifier yet.",
        )

    system_quantity = _available_stock(session, payload.sku_id, payload.warehouse)
    variance = payload.physical_quantity - system_quantity
    return InventoryAuditRead(
        audit_id=uuid4(),
        sku_id=payload.sku_id,
        warehouse=payload.warehouse,
        client_id=client_id,
        product_id=sku.sku,
        product_category=sku.category,
        system_quantity=system_quantity,
        physical_quantity=payload.physical_quantity,
        variance_quantity=variance,
        discrepancy_detected=variance != 0,
    )


# ---------------------------------------------------------------------------
# Movements
# ---------------------------------------------------------------------------


@router.post(
    "/orders/inbound",
    response_model=StockEntryRead,
    status_code=status.HTTP_201_CREATED,
    summary="Register a goods receipt",
)
def create_inbound(
    payload: StockEntryCreate,
    session: Session = Depends(get_db),
    caller: UserInDB = Depends(get_current_user),
) -> StockEntryRead:
    """A receipt from a client brand. Adds stock; never rejected on stock
    grounds, since it can only increase the figure.

    Still takes the same row lock as an exit. A receipt landing between
    another request's stock check and its insert would not cause an
    oversell — it can only add units — but taking the lock keeps every
    write to one SKU serialised, so the movement history cannot
    interleave in ways that are hard to reason about later.
    """
    _lock_sku_or_404(session, payload.sku_id)

    entry = StockEntry(
        sku_id=payload.sku_id,
        quantity=payload.quantity,
        reference=payload.reference,
        warehouse=payload.warehouse,
        # From TinyDB, never from the request body — the caller does not
        # get to say who confirmed the receipt.
        user_uuid=str(caller.id),
    )
    session.add(entry)
    session.commit()
    session.refresh(entry)

    return StockEntryRead.model_validate(entry)


@router.post(
    "/orders/outbound",
    response_model=StockExitRead,
    status_code=status.HTTP_201_CREATED,
    summary="Register a dispatch or a loss",
)
def create_outbound(
    payload: StockExitCreate,
    session: Session = Depends(get_db),
    caller: UserInDB = Depends(get_current_user),
) -> StockExitRead:
    """A dispatch to a customer, or a written-off loss.

    The stock check happens **before** anything is written. A rejected
    exit must leave the database exactly as it found it — a partially
    applied movement would corrupt every later stock figure, and for
    TrackFlow a stock discrepancy is a contractual problem, not an
    internal one.

    The check is scoped to the warehouse on the exit. Units in Zaragoza
    cannot satisfy a dispatch from Los Angeles (CONTEXT rule 6).
    """
    # Locks the SKU row for the duration of this transaction, so the
    # check below and the insert that follows cannot be interleaved by a
    # second dispatch. See _lock_sku_or_404.
    sku = _lock_sku_or_404(session, payload.sku_id)

    available = _available_stock(session, payload.sku_id, payload.warehouse)
    if payload.quantity > available:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            # Wording fixed by CONTEXT rule 2.
            detail=(
                f"Insufficient stock for SKU '{sku.sku}'. "
                f"Available: {available}, requested: {payload.quantity}."
            ),
        )

    movement = StockExit(
        sku_id=payload.sku_id,
        quantity=payload.quantity,
        exit_type=payload.exit_type,
        tracking_number=payload.tracking_number,
        warehouse=payload.warehouse,
        user_uuid=str(caller.id),
    )
    session.add(movement)
    session.commit()
    session.refresh(movement)

    return StockExitRead.model_validate(movement)


@router.get(
    "/orders",
    response_model=list[MovementRead],
    summary="List all stock movements with their SKU",
)
def list_orders(
    warehouse: Warehouse | None = Query(default=None),
    movement_type: str | None = Query(
        default=None, description="Filter to 'entry' or 'exit'."
    ),
    session: Session = Depends(get_db),
    _caller: UserInDB = Depends(get_current_user),
) -> list[MovementRead]:
    """Entries and exits interleaved, newest first, each with its SKU.

    Deliberately N+1 free, and visibly so. The movements are read first,
    then every SKU they mention is fetched in **one** query and indexed
    by id. The alternative — reading `movement.sku` inside the loop —
    emits one query per row: invisible on six seed movements, and the
    slowest endpoint in the service once a warehouse has a year of
    history behind it.

    Three queries total regardless of how many movements come back:
    entries, exits, and the SKUs.
    """
    entries: list[StockEntry] = []
    exits: list[StockExit] = []

    if movement_type in (None, "entry"):
        entry_query = select(StockEntry)
        if warehouse is not None:
            entry_query = entry_query.where(StockEntry.warehouse == warehouse)
        entries = list(session.exec(entry_query).all())

    if movement_type in (None, "exit"):
        exit_query = select(StockExit)
        if warehouse is not None:
            exit_query = exit_query.where(StockExit.warehouse == warehouse)
        exits = list(session.exec(exit_query).all())

    # One query for every SKU referenced by either list.
    sku_ids = {m.sku_id for m in entries} | {m.sku_id for m in exits}
    skus: dict[int, SKU] = {}
    if sku_ids:
        rows = session.exec(select(SKU).where(col(SKU.id).in_(sku_ids))).all()
        skus = {s.id: s for s in rows if s.id is not None}

    movements: list[MovementRead] = []

    for entry in entries:
        sku = skus.get(entry.sku_id)
        if sku is None or entry.id is None:
            continue
        movements.append(
            MovementRead(
                movement_type="entry",
                id=entry.id,
                quantity=entry.quantity,
                warehouse=entry.warehouse,
                created_at=entry.created_at,
                user_uuid=entry.user_uuid,
                sku=SKUSummary.model_validate(sku),
                reference=entry.reference,
            )
        )

    for movement in exits:
        sku = skus.get(movement.sku_id)
        if sku is None or movement.id is None:
            continue
        movements.append(
            MovementRead(
                movement_type="exit",
                id=movement.id,
                quantity=movement.quantity,
                warehouse=movement.warehouse,
                created_at=movement.created_at,
                user_uuid=movement.user_uuid,
                sku=SKUSummary.model_validate(sku),
                exit_type=movement.exit_type,
                tracking_number=movement.tracking_number,
            )
        )

    movements.sort(key=lambda m: m.created_at, reverse=True)
    return movements
