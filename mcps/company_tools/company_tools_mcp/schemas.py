"""Structured MCP output contracts grounded in TrackFlow's existing APIs."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class IncidentRecord(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: int
    title: str | None = None
    description: str | None = None
    category: str
    status: str
    origin: str
    branch: str
    created_at: str | None = None
    updated_at: str | None = None


class InventoryProduct(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: int
    name: str
    sku: str
    warehouse: str
    current_stock: int
    client_name: str | None = None
    category: str | None = None
    stock_by_warehouse: dict[str, int] = Field(default_factory=dict)
    minimum_stock: int | None = None


class InventoryQueryResult(BaseModel):
    products: list[InventoryProduct]
    count: int
    read_only: bool = True


class RejectedInventoryWrite(BaseModel):
    error: str
    operation: str
    target: str
    details: dict[str, Any] = Field(default_factory=dict)
