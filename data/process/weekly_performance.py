"""Pure transformation for TrackFlow's weekly business-performance report."""

from __future__ import annotations

import json
from collections import defaultdict
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

BUSINESS_EVENT_TYPES = frozenset(
    {
        "inbound_order_created",
        "outbound_order_created",
        "stock_threshold_triggered",
        "inventory_discrepancy_detected",
    }
)
WAREHOUSES = frozenset({"los_angeles", "zaragoza"})
PRODUCT_CATEGORIES = frozenset({"fashion", "electronics", "cosmetics"})


class PipelineQualityError(ValueError):
    """The source population cannot safely produce a business report."""


def _utc_datetime(value: Any) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    else:
        raise PipelineQualityError("timestamp must be an ISO 8601 datetime")
    if parsed.tzinfo is None:
        raise PipelineQualityError("timestamp must include a UTC offset")
    return parsed.astimezone(UTC)


def _logical_event_id(tags: dict[str, Any]) -> str:
    value = tags.get("event_id")
    try:
        return str(UUID(str(value)))
    except (TypeError, ValueError, AttributeError) as exc:
        raise PipelineQualityError("event_id must be a UUID") from exc


def _validated_dimensions(event: dict[str, Any]) -> tuple[str, str, datetime, int]:
    event_type = event.get("event_type")
    if event_type not in BUSINESS_EVENT_TYPES:
        raise PipelineQualityError(f"unsupported business event type: {event_type!r}")

    tags = event.get("tags")
    if not isinstance(tags, dict):
        raise PipelineQualityError("tags must be an object")

    warehouse = tags.get("warehouse")
    if warehouse not in WAREHOUSES:
        raise PipelineQualityError("warehouse must be los_angeles or zaragoza")

    client_id = tags.get("client_id")
    product_id = tags.get("product_id")
    product_category = tags.get("product_category")
    if not isinstance(client_id, str) or not client_id.strip():
        raise PipelineQualityError("client_id must be a non-empty opaque id")
    if not isinstance(product_id, str) or not product_id.strip():
        raise PipelineQualityError("product_id must be a non-empty opaque id")
    if product_category not in PRODUCT_CATEGORIES:
        raise PipelineQualityError("product_category is not a TrackFlow category")

    quantity = tags.get("quantity")
    if not isinstance(quantity, int) or isinstance(quantity, bool):
        raise PipelineQualityError("quantity must be an integer")
    minimum = 0 if event_type == "stock_threshold_triggered" else 1
    if quantity < minimum:
        raise PipelineQualityError(f"quantity must be at least {minimum}")

    return warehouse, client_id.strip(), _utc_datetime(event.get("timestamp")), quantity


def _canonical_event(event: dict[str, Any]) -> str:
    """Stable payload used to distinguish a retry from an ID collision."""
    return json.dumps(
        {
            "timestamp": _utc_datetime(event.get("timestamp")).isoformat(),
            "event_type": event.get("event_type"),
            "tags": event.get("tags"),
        },
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )


def _week_start(timestamp: datetime) -> date:
    return date.fromordinal(timestamp.date().toordinal() - timestamp.weekday())


def transform_weekly_performance(events: list[dict[str, Any]]) -> dict[str, Any]:
    """Validate, deduplicate, and aggregate the four approved business events.

    The function has no database or filesystem access so the Prefect task can
    cache it safely. Any malformed row or conflicting duplicate aborts the
    publication instead of silently turning unknown coverage into a zero.
    """
    seen: dict[str, str] = {}
    duplicate_count = 0
    groups: dict[tuple[str, str, date], dict[str, int]] = defaultdict(
        lambda: {
            "inbound_units_count": 0,
            "outbound_orders_count": 0,
            "stockout_events_count": 0,
            "discrepancy_events_count": 0,
        }
    )

    for event in events:
        if not isinstance(event, dict):
            raise PipelineQualityError("every extracted event must be an object")
        tags = event.get("tags")
        if not isinstance(tags, dict):
            raise PipelineQualityError("tags must be an object")

        event_id = _logical_event_id(tags)
        canonical = _canonical_event(event)
        if event_id in seen:
            if seen[event_id] != canonical:
                raise PipelineQualityError(
                    "the same event_id has conflicting timestamps or business payloads"
                )
            duplicate_count += 1
            continue
        seen[event_id] = canonical

        warehouse, client_id, timestamp, quantity = _validated_dimensions(event)
        group = groups[(warehouse, client_id, _week_start(timestamp))]
        event_type = event["event_type"]
        if event_type == "inbound_order_created":
            group["inbound_units_count"] += quantity
        elif event_type == "outbound_order_created":
            group["outbound_orders_count"] += 1
        elif event_type == "stock_threshold_triggered":
            group["stockout_events_count"] += 1
        else:
            group["discrepancy_events_count"] += 1

    rows: list[dict[str, Any]] = []
    review_flags: list[dict[str, Any]] = []
    for (warehouse, client_id, week_start), counters in sorted(groups.items()):
        outbound = counters["outbound_orders_count"]
        discrepancies = counters["discrepancy_events_count"]
        rate = Decimal(discrepancies) / Decimal(outbound) if outbound else Decimal(0)
        row = {
            "warehouse": warehouse,
            "client_id": client_id,
            "week_start": week_start,
            **counters,
            "discrepancy_rate": rate,
        }
        rows.append(row)
        if discrepancies > outbound:
            review_flags.append(
                {
                    "warehouse": warehouse,
                    "client_id": client_id,
                    "week_start": week_start.isoformat(),
                    "reason": "discrepancies_exceed_outbound_orders",
                }
            )

    return {
        "rows": rows,
        "records_processed": len(events),
        "records_accepted": len(seen),
        "deduplicated": duplicate_count,
        "rejected": 0,
        "quality_summary": {
            "coverage_state": "validated",
            "review_flags": review_flags,
        },
    }
