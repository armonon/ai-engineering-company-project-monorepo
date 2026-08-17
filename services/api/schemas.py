"""Pydantic request/response schemas for the inventory API.

Deliberately a separate file from `models.py`, and deliberately
different classes. The ORM models describe what Supabase stores; these
describe what the API accepts and returns. They overlap, but they are
not the same thing, and no endpoint ever returns a raw SQLModel object:

  * `SKURead` carries `current_stock`, which no table has — it is
    computed from the movements on every read (CONTEXT rule 1).
  * `SKUCreate` omits `id`, which the database assigns.
  * The movement create-schemas omit `user_uuid` and `created_at`: the
    caller does not get to choose who created a record or when. Both are
    filled in by the route from the authenticated TinyDB user and the
    server clock.

Names follow CONTEXT-trackflow.md exactly — SKU, StockEntry, StockExit.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from models import ExitType, SKUCategory, Warehouse

# ---------------------------------------------------------------------------
# SKU
# ---------------------------------------------------------------------------


class SKUCreate(BaseModel):
    """Registering a new SKU. No stock field — see the module docstring."""

    name: str = Field(min_length=1, max_length=200)
    sku: str = Field(min_length=1, max_length=60)
    client_name: str = Field(min_length=1, max_length=120)
    category: SKUCategory
    warehouse: Warehouse

    @field_validator("name", "sku", "client_name")
    @classmethod
    def _strip(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("must not be blank")
        return cleaned


class SKURead(BaseModel):
    """A SKU as the API returns it, with stock computed at read time.

    `current_stock` is scoped to this SKU's own warehouse. TrackFlow
    holds the same product in two warehouses as two SKU rows, and rule 6
    is explicit that 20 units in LA and 15 in Zaragoza is two figures,
    not 35.

    `stock_by_warehouse` is included as well, so the per-warehouse
    breakdown is visible rather than implied — CONTEXT asks for the
    choice to be documented, and showing both makes it self-documenting.
    In clean data it holds a single entry matching `warehouse`.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    sku: str
    client_name: str
    category: SKUCategory
    warehouse: Warehouse
    current_stock: int
    stock_by_warehouse: dict[str, int] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# StockEntry — goods receipts (inbound)
# ---------------------------------------------------------------------------


class StockEntryCreate(BaseModel):
    sku_id: int
    quantity: int = Field(gt=0, description="Units received; must be positive.")
    reference: str = Field(min_length=1, max_length=60)
    warehouse: Warehouse

    @field_validator("reference")
    @classmethod
    def _strip(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("reference must not be blank")
        return cleaned


class StockEntryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    sku_id: int
    quantity: int
    reference: str
    warehouse: Warehouse
    created_at: datetime
    user_uuid: str


# ---------------------------------------------------------------------------
# StockExit — dispatches and losses (outbound)
# ---------------------------------------------------------------------------


class StockExitCreate(BaseModel):
    sku_id: int
    quantity: int = Field(gt=0, description="Units dispatched or written off.")
    exit_type: ExitType
    tracking_number: str | None = Field(default=None, max_length=60)
    warehouse: Warehouse

    @model_validator(mode="after")
    def _tracking_matches_exit_type(self) -> StockExitCreate:
        """CONTEXT rule 3, enforced in both directions.

        A dispatch without a tracking number is an untraceable parcel; a
        loss *with* one implies a carrier movement that never happened.
        Rejecting both keeps the two exit types meaningfully distinct.
        """
        tracking = (self.tracking_number or "").strip() or None

        if self.exit_type is ExitType.DISPATCH and tracking is None:
            raise ValueError(
                "tracking_number is required when exit_type is 'dispatch'"
            )
        if self.exit_type is ExitType.LOSS and tracking is not None:
            raise ValueError("tracking_number must be null when exit_type is 'loss'")

        self.tracking_number = tracking
        return self


class StockExitRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    sku_id: int
    quantity: int
    exit_type: ExitType
    tracking_number: str | None
    warehouse: Warehouse
    created_at: datetime
    user_uuid: str


# ---------------------------------------------------------------------------
# Combined movement feed — GET /inventory/orders
# ---------------------------------------------------------------------------


class SKUSummary(BaseModel):
    """The SKU fields embedded in a movement row.

    Enough to read the feed without a second call, without repeating the
    whole SKU record on every line.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    sku: str
    client_name: str


class MovementRead(BaseModel):
    """One row of the unified movement feed.

    Entries and exits are different tables, so the feed flattens them
    into a common shape with a `movement_type` discriminator. Fields that
    only apply to one kind are null on the other.
    """

    movement_type: str = Field(description="'entry' (inbound) or 'exit' (outbound)")
    id: int
    quantity: int
    warehouse: Warehouse
    created_at: datetime
    user_uuid: str
    sku: SKUSummary
    reference: str | None = None
    exit_type: ExitType | None = None
    tracking_number: str | None = None
