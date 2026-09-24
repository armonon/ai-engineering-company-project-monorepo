"""Pydantic models for the TrackFlow supplier directory.

Every field name, category, and status here is transcribed directly
from CONTEXT.md § "Supplier model". Do not rename or extend without
changing the CONTEXT first — the API contract and the seeder both
depend on these exact strings.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum

from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator

# ---------------------------------------------------------------------------
# Enumerations — the closed value sets from CONTEXT.md
# ---------------------------------------------------------------------------


class Country(str, Enum):
    """Contract country. TrackFlow operates in exactly two markets."""

    USA = "USA"
    SPAIN = "Spain"


class Currency(str, Enum):
    USD = "USD"
    EUR = "EUR"


class Status(str, Enum):
    """CONTEXT: VALID_STATUSES = ["active", "suspended"].

    Suppliers are suspended, never deleted, when incident rates spike —
    the suspension history is operationally relevant.
    """

    ACTIVE = "active"
    SUSPENDED = "suspended"


class Category(str, Enum):
    """CONTEXT: VALID_CATEGORIES — all eight, verbatim."""

    CARRIER_LAST_MILE = "carrier_last_mile"
    CARRIER_INTERNATIONAL = "carrier_international"
    WAREHOUSE_SUPPLIES = "warehouse_supplies"
    PACKAGING_MATERIALS = "packaging_materials"
    REVERSE_LOGISTICS = "reverse_logistics"
    FLEET_MAINTENANCE = "fleet_maintenance"
    IT_AND_WMS_SOFTWARE = "it_and_wms_software"
    CLEANING_AND_FACILITIES = "cleaning_and_facilities"


# CONTEXT § Business constraints: "A supplier from 'USA' must have
# currency = 'USD'. A supplier from 'Spain' must have currency = 'EUR'."
CURRENCY_FOR_COUNTRY: dict[Country, Currency] = {
    Country.USA: Currency.USD,
    Country.SPAIN: Currency.EUR,
}


def utcnow() -> datetime:
    return datetime.now(UTC)


# ---------------------------------------------------------------------------
# Input models
# ---------------------------------------------------------------------------


class SupplierBase(BaseModel):
    """Fields a client is allowed to send.

    `updated_at` is deliberately absent — it is system-generated
    (CONTEXT: "datetime, system-generated").
    """

    name: str = Field(..., min_length=1, description="Supplier trade name")
    country: Country = Field(..., description="Contract country: USA or Spain")
    categories: list[Category] = Field(
        ...,
        min_length=1,
        description="Type of service or product supplied. At least one.",
    )
    rate_per_shipment: float = Field(
        ...,
        gt=0,
        description=(
            "Current rate per shipment or service unit in the contract "
            "currency. Must be greater than zero."
        ),
    )
    currency: Currency = Field(..., description="USD for USA, EUR for Spain")
    status: Status = Field(
        default=Status.ACTIVE, description="active or suspended"
    )
    service_zone: str | None = Field(
        default=None, description="Supplier coverage zone, e.g. 'West Coast'"
    )
    contact_email: str | None = Field(
        default=None, description="Supplier contact email"
    )
    notes: str | None = Field(default=None, description="Operations team notes")

    @field_validator("name")
    @classmethod
    def _strip_name(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("name cannot be blank")
        return stripped

    @field_validator("categories")
    @classmethod
    def _no_duplicate_categories(cls, value: list[Category]) -> list[Category]:
        # Preserve order, drop repeats — "carrier_last_mile" twice is a
        # client bug, not a meaningful distinction.
        seen: list[Category] = []
        for category in value:
            if category not in seen:
                seen.append(category)
        return seen

    @model_validator(mode="after")
    def _currency_matches_country(self) -> SupplierBase:
        expected = CURRENCY_FOR_COUNTRY[self.country]
        if self.currency != expected:
            raise ValueError(
                f"currency must be '{expected.value}' for country "
                f"'{self.country.value}', got '{self.currency.value}'"
            )
        return self


class SupplierCreate(SupplierBase):
    """POST /suppliers body."""


class RateUpdate(BaseModel):
    """PATCH /suppliers/{id}/rate body.

    CONTEXT: "Do not accept rates equal to or less than zero."
    """

    rate_per_shipment: float = Field(
        ..., gt=0, description="New rate. Must be greater than zero."
    )


class StatusUpdate(BaseModel):
    """PATCH /suppliers/{id}/status body.

    Typed as the Status enum, so any value outside
    {"active", "suspended"} is rejected with 422 before it can reach
    TinyDB.
    """

    status: Status = Field(..., description="active or suspended")


# ---------------------------------------------------------------------------
# Response model
# ---------------------------------------------------------------------------


class SupplierOut(SupplierBase):
    """What the API returns: the stored record plus its TinyDB id and
    the system-generated `updated_at`."""

    id: int = Field(..., description="TinyDB-assigned document id")
    updated_at: datetime = Field(
        ..., description="Timestamp of the last rate update (system-generated)"
    )


class DeleteResponse(BaseModel):
    id: int
    deleted: bool
    message: str


# ===========================================================================
# Authentication — User and Profile
#
# Both live in TinyDB only. Other stores (PostgreSQL and friends, later)
# reference the TinyDB user `id` as `user_uuid` and never hold a copy of
# the account itself.
#
# Deliberate split: `User` holds credentials, `Profile` holds who the
# person is. Display name and contact details are on Profile, never on
# User.
# ===========================================================================


class Role(str, Enum):
    """Only these three values are accepted. New registrations default
    to `user`; elevating a role is an admin-only action."""

    ADMIN = "admin"
    MANAGER = "manager"
    USER = "user"


# --- input models ----------------------------------------------------------


class UserCreate(BaseModel):
    """POST /users body.

    Accepts optional initial profile fields so registration creates the
    User and its linked Profile in one operation.
    """

    email: EmailStr = Field(..., description="Login identity. Must be unique.")
    password: str = Field(
        ..., min_length=8, description="Plain text in, hashed before storage."
    )

    # Optional initial profile — stored on Profile, not on User.
    name: str | None = Field(default=None, description="Display name (Profile).")
    phone: str | None = Field(default=None, description="Contact phone (Profile).")
    address: str | None = Field(default=None, description="Contact address (Profile).")

    @field_validator("email")
    @classmethod
    def _normalise_email(cls, value: str) -> str:
        # Emails are case-insensitive in practice; store one canonical form
        # so 'A@x.com' and 'a@x.com' cannot become two accounts.
        return value.strip().lower()


class UserUpdate(BaseModel):
    """PUT /users/{id} body — credential fields only.

    `role` is accepted here but only honoured for admin callers; the
    route enforces that.
    """

    email: EmailStr | None = None
    password: str | None = Field(default=None, min_length=8)
    role: Role | None = None
    is_active: bool | None = None

    @field_validator("email")
    @classmethod
    def _normalise_email(cls, value: str | None) -> str | None:
        return value.strip().lower() if value else value


class ProfileUpdate(BaseModel):
    """PUT /profiles/me body."""

    name: str | None = None
    phone: str | None = None
    address: str | None = None


class LoginRequest(BaseModel):
    """POST /auth/login body (JSON variant)."""

    email: EmailStr
    password: str

    @field_validator("email")
    @classmethod
    def _normalise_email(cls, value: str) -> str:
        return value.strip().lower()


# --- stored / output models ------------------------------------------------


class UserInDB(BaseModel):
    """The full stored record, hash included. Never returned by a route."""

    id: int
    email: EmailStr
    hashed_password: str
    is_active: bool = True
    role: Role = Role.USER
    created_at: datetime


class UserOut(BaseModel):
    """What routes return — no password material, ever."""

    id: int
    email: EmailStr
    is_active: bool
    role: Role
    created_at: datetime


class ProfileOut(BaseModel):
    id: int
    user_id: int
    name: str | None = None
    phone: str | None = None
    address: str | None = None


class MeOut(BaseModel):
    """GET /auth/me — credentials plus the linked profile."""

    id: int
    email: EmailStr
    role: Role
    is_active: bool
    telemetry_user_id: str = Field(
        ...,
        description="Pseudonymous identifier for telemetry; never the TinyDB id.",
    )
    profile: ProfileOut | None = None


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int = Field(..., description="Token lifetime in seconds.")
    telemetry_user_id: str = Field(
        ...,
        description="Pseudonymous telemetry identity; never the raw TinyDB id.",
    )
    role: Role


# ---------------------------------------------------------------------------
# Password reset / change (AUTH-03)
# ---------------------------------------------------------------------------


class ForgotPasswordRequest(BaseModel):
    """POST /auth/forgot-password.

    The response is always 200 regardless of whether this address is
    registered, so the endpoint cannot be used to enumerate accounts.
    """

    email: EmailStr

    @field_validator("email")
    @classmethod
    def _normalise_email(cls, value: str) -> str:
        return value.strip().lower()


class ResetPasswordRequest(BaseModel):
    """POST /auth/reset-password."""

    token: str = Field(..., min_length=1, description="Token from the reset link.")
    new_password: str = Field(
        ..., min_length=8, description="Plain text in, hashed before storage."
    )


class ChangePasswordRequest(BaseModel):
    """POST /auth/change-password — requires a valid session."""

    current_password: str = Field(..., min_length=1)
    new_password: str = Field(..., min_length=8)


class MessageResponse(BaseModel):
    message: str


# ===========================================================================
# Inventory — SQLModel ORM models (Milestone 5)
#
# These are the *only* SQLModel `table=True` classes in the codebase, and
# they are the only things that live in Supabase. Everything above this
# line is a Pydantic model held in TinyDB or used as an API contract.
#
# Names come from CONTEXT-trackflow.md § "Entity Names and Field
# Specification" and are not interchangeable with the README's generic
# Product / InboundOrder / OutboundOrder: TrackFlow calls them SKU,
# StockEntry and StockExit, and the API speaks that language.
#
# Note what is NOT here: a User table. Auth stays in TinyDB, and both
# movement models carry `user_uuid` as a plain string referencing the
# TinyDB user id — no foreign key, no replicated account (CONTEXT rule 4).
#
# `current_stock` is also deliberately absent. It is derived from the
# movements, never stored, so there is no column anyone could set
# directly (CONTEXT rule 1). It appears only on the response schema in
# schemas.py.
# ===========================================================================

from sqlmodel import Field as SQLField  # noqa: E402
from sqlmodel import SQLModel  # noqa: E402


class Warehouse(str, Enum):
    """CONTEXT § "Los Angeles and Zaragoza warehouses coexist"."""

    LA = "LA"
    ZGZ = "ZGZ"


class SKUCategory(str, Enum):
    """CONTEXT § SKU.category."""

    FASHION = "fashion"
    ELECTRONICS = "electronics"
    COSMETICS = "cosmetics"


class ExitType(str, Enum):
    """CONTEXT § StockExit.exit_type."""

    DISPATCH = "dispatch"
    LOSS = "loss"


class SKU(SQLModel, table=True):
    """A client brand's product line, held at one warehouse.

    The same physical product in two warehouses is two SKU rows with
    distinct `sku` codes — see the seed data, where the white sneaker is
    CLT-SNK-W-42 in LA and CLT-SNK-W-42-Z in Zaragoza. That is what makes
    stock per-warehouse rather than global (CONTEXT rule 6).
    """

    __tablename__ = "sku"

    id: int | None = SQLField(default=None, primary_key=True)
    name: str = SQLField(index=True)
    sku: str = SQLField(index=True, unique=True)
    client_name: str = SQLField(index=True)
    category: SKUCategory
    warehouse: Warehouse = SQLField(index=True)

    # No SQLModel `Relationship()` here on purpose. This module uses
    # `from __future__ import annotations`, which turns every annotation
    # into a string; SQLAlchemy then reads `list["StockEntry"]` as a
    # class literally named that and fails to map it. The foreign keys
    # below are the real relationship and are enforced by the database.
    # `routers/inventory.py` loads related SKUs with one explicit extra
    # query, which avoids N+1 without depending on lazy attribute
    # access — and is easier to reason about than relationship loading.


class StockEntry(SQLModel, table=True):
    """A goods receipt: stock arriving from a client brand."""

    __tablename__ = "stock_entry"

    id: int | None = SQLField(default=None, primary_key=True)
    # Enforced at database level, per the acceptance criteria.
    sku_id: int = SQLField(foreign_key="sku.id", index=True)
    quantity: int
    reference: str
    warehouse: Warehouse = SQLField(index=True)
    created_at: datetime = SQLField(default_factory=lambda: datetime.now(UTC))
    # TinyDB user id as a string. No FK — there is no user table here.
    user_uuid: str = SQLField(index=True)


class StockExit(SQLModel, table=True):
    """A dispatch to a customer, or a written-off loss."""

    __tablename__ = "stock_exit"

    id: int | None = SQLField(default=None, primary_key=True)
    sku_id: int = SQLField(foreign_key="sku.id", index=True)
    quantity: int
    exit_type: ExitType
    # Required for a dispatch, must be null for a loss (CONTEXT rule 3).
    tracking_number: str | None = SQLField(default=None)
    warehouse: Warehouse = SQLField(index=True)
    created_at: datetime = SQLField(default_factory=lambda: datetime.now(UTC))
    user_uuid: str = SQLField(index=True)
