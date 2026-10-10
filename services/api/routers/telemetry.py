"""Persistent, partially accepting telemetry ingestion for TrackFlow.

The browser contract stays ``POST /telemetry/events`` with
``{"events": [...]}``. Only the backend behaviour changes: each item is
validated independently against the unchanged ``TelemetryEvent`` model and
the approved event catalogue, then all valid rows are written with one bulk
INSERT. Invalid items are counted without poisoning the rest of the batch.
"""

from __future__ import annotations

import json
import logging
import math
import os
import re
from decimal import Decimal
from functools import lru_cache
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends
from pydantic import ValidationError
from sqlalchemy import insert
from sqlmodel import Session

from database import get_db
from models import TelemetryEventRecord
from schemas import TelemetryEvent, TelemetryIngestBatch, TelemetryReceipt

# Use Uvicorn's configured application logger so safe operational metadata is
# visible in the development server and tests. Event properties are never
# logged, including rejected payloads.
logger = logging.getLogger("uvicorn.error.trackflow.telemetry")

router = APIRouter(prefix="/telemetry", tags=["telemetry"])

_CATALOGUE_PATH = (
    Path(__file__).resolve().parents[3] / "docs" / "telemetry" / "event-schemas.json"
)

_API_EVENT_TYPES = {
    "direct_stock_edit_rejected",
    "api_latency_recorded",
    "api_error_returned",
}
_ERROR_EVENT_TYPES = {"frontend_error_captured", "api_error_returned"}
_WARN_EVENT_TYPES = {
    "authorization_denied",
    "direct_stock_edit_rejected",
    "inventory_discrepancy_detected",
    "inventory_validation_failed",
    "login_failed",
    "outbound_order_rejected",
    "session_expired",
    "stock_threshold_triggered",
}
_VALUE_PROPERTY_BY_EVENT = {
    "api_error_returned": "duration_ms",
    "api_latency_recorded": "duration_ms",
    "audit_history_viewed": "load_duration_ms",
    "direct_stock_edit_rejected": "quantity",
    "frontend_error_captured": "occurrence_count",
    "inbound_order_created": "quantity",
    "inventory_discrepancy_detected": "variance_quantity",
    "inventory_loss_recorded": "quantity",
    "inventory_validation_failed": "occurrence_count",
    "outbound_order_created": "quantity",
    "outbound_order_rejected": "quantity",
    "page_load_recorded": "duration_ms",
    "product_created": "quantity",
    "stock_threshold_triggered": "quantity",
    "workflow_abandoned": "duration_ms",
    "workflow_completed": "duration_ms",
}


def telemetry_endpoint() -> str:
    """Read the configured public receiver URL, never a credential."""
    return os.environ.get(
        "TELEMETRY_ENDPOINT", "http://localhost:8000/telemetry/events"
    ).strip()


@lru_cache(maxsize=1)
def _catalogue_events() -> dict[str, dict[str, Any]]:
    """Load the approved Phase 1 event catalogue once per process."""
    with _CATALOGUE_PATH.open(encoding="utf-8") as catalogue_file:
        document = json.load(catalogue_file)
    events = document.get("events")
    if not isinstance(events, dict):
        raise RuntimeError("event-schemas.json does not contain an events object")
    return events


def _matches_property_type(value: Any, expected: str) -> bool:
    if expected == "string":
        return isinstance(value, str)
    if expected == "boolean":
        return isinstance(value, bool)
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "number":
        return (
            isinstance(value, (int, float, Decimal))
            and not isinstance(value, bool)
            and (not isinstance(value, float) or math.isfinite(value))
        )
    return False


def _property_matches_rule(value: Any, rule: dict[str, Any]) -> bool:
    if not _matches_property_type(value, str(rule.get("type", ""))):
        return False

    if "enum" in rule and value not in rule["enum"]:
        return False
    if isinstance(value, str):
        if len(value) < int(rule.get("minLength", 0)):
            return False
        pattern = rule.get("pattern")
        if pattern is not None and re.fullmatch(str(pattern), value) is None:
            return False
        if rule.get("format") == "uuid":
            try:
                UUID(value)
            except (TypeError, ValueError, AttributeError):
                return False
    if isinstance(value, (int, float, Decimal)) and not isinstance(value, bool):
        if "minimum" in rule and value < rule["minimum"]:
            return False
        if "maximum" in rule and value > rule["maximum"]:
            return False
    return True


def event_matches_catalogue(event: TelemetryEvent) -> bool:
    """Validate the event-specific allowlist without changing its model.

    ``TelemetryEvent`` remains the exact Phase 2 envelope contract. The
    catalogue adds the per-event required keys, types, enums, ranges, and
    patterns documented in ``telemetry-plan.md``.
    """
    specification = _catalogue_events().get(event.event_type)
    if specification is None:
        return False
    if specification.get("event_type") != event.event_type:
        return False
    if specification.get("schemaVersion") != event.schemaVersion:
        return False

    property_spec = specification.get("properties", {})
    fields = property_spec.get("fields", {})
    if not isinstance(fields, dict):
        return False

    keys = set(event.properties)
    allowed = set(fields)
    if property_spec.get("additionalProperties") is False and keys - allowed:
        return False

    for name, rule in fields.items():
        if not isinstance(rule, dict):
            return False
        if rule.get("required") is True and name not in event.properties:
            return False
        if name in event.properties and not _property_matches_rule(
            event.properties[name], rule
        ):
            return False
    return True


def _service_for(event: TelemetryEvent) -> str:
    if (
        event.event_type in _API_EVENT_TYPES
        or event.properties.get("service") == "trackflow_api"
    ):
        return "api"
    return "backoffice"


def _level_for(event: TelemetryEvent) -> str:
    if event.event_type in _ERROR_EVENT_TYPES:
        return "error"
    if event.event_type in _WARN_EVENT_TYPES:
        return "warn"
    return "info"


def _value_for(event: TelemetryEvent) -> Decimal | None:
    property_name = _VALUE_PROPERTY_BY_EVENT.get(event.event_type)
    if property_name is None:
        return None
    value = event.properties.get(property_name)
    if not isinstance(value, (int, float, Decimal)) or isinstance(value, bool):
        return None
    return Decimal(str(value))


def event_to_row(event: TelemetryEvent) -> dict[str, Any]:
    """Map an approved event to the eight-column storage contract."""
    tags = dict(event.properties)
    tags.update(
        {
            "event_id": str(event.eventId),
            "session_id": event.sessionId,
            "user_id": event.userId,
            "schema_version": event.schemaVersion,
            "request_id": event.requestId,
        }
    )
    return {
        # Supplying the UUID keeps SQLite tests portable; PostgreSQL still has
        # the required gen_random_uuid() default for non-application inserts.
        "id": uuid4(),
        "timestamp": event.timestamp,
        "service": _service_for(event),
        "event_type": event.event_type,
        "level": _level_for(event),
        "value": _value_for(event),
        "message": None,
        "tags": tags,
    }


def persist_telemetry_events(
    session: Session,
    events: list[TelemetryEvent],
    *,
    received: int,
    rejected: int,
) -> TelemetryReceipt:
    """Write all valid events with one executemany INSERT and one commit."""
    rows = [event_to_row(event) for event in events]
    if rows:
        try:
            # Core table insert keeps nullable keys in every parameter set,
            # so heterogeneous event types still use one executemany call.
            # ORM bulk insert otherwise groups rows by their non-null columns
            # and silently emits multiple INSERT statements.
            session.execute(insert(TelemetryEventRecord.__table__), rows)
            session.commit()
        except Exception:
            session.rollback()
            raise

    event_types = [event.event_type for event in events]
    logger.info(
        "Telemetry batch stored received=%d stored=%d rejected=%d "
        "event_types=%s endpoint=%s",
        received,
        len(rows),
        rejected,
        event_types,
        telemetry_endpoint(),
    )
    return TelemetryReceipt(
        received=received,
        stored=len(rows),
        rejected=rejected,
    )


def persist_internal_event(session: Session, event: TelemetryEvent) -> TelemetryReceipt:
    """Store one server-originated event through the same catalogue gate."""
    if not event_matches_catalogue(event):
        logger.warning(
            "Internal telemetry event rejected event_type=%s",
            event.event_type,
        )
        return TelemetryReceipt(received=1, stored=0, rejected=1)
    return persist_telemetry_events(
        session,
        [event],
        received=1,
        rejected=0,
    )


@router.post(
    "/events",
    response_model=TelemetryReceipt,
    summary="Validate and persist a telemetry batch",
)
def receive_events(
    batch: TelemetryIngestBatch,
    session: Session = Depends(get_db),
) -> TelemetryReceipt:
    valid: list[TelemetryEvent] = []
    rejected = 0

    for raw_event in batch.events:
        try:
            event = TelemetryEvent.model_validate(raw_event)
        except ValidationError:
            rejected += 1
            continue
        if not event_matches_catalogue(event):
            rejected += 1
            continue
        valid.append(event)

    return persist_telemetry_events(
        session,
        valid,
        received=len(batch.events),
        rejected=rejected,
    )
