"""Temporary telemetry receiver for capture-pipeline verification.

This phase deliberately does not persist events. It validates the standard
envelope, logs only the batch size and registered event-type labels, and
returns the count. Phase 3 replaces this receiver without changing clients.
"""

from __future__ import annotations

import logging
import os

from fastapi import APIRouter

from schemas import TelemetryBatch, TelemetryReceipt

# Use Uvicorn's configured application logger so verification metadata is
# visible in the real development-server console as well as in tests.
logger = logging.getLogger("uvicorn.error.trackflow.telemetry")

router = APIRouter(prefix="/telemetry", tags=["telemetry"])


def telemetry_endpoint() -> str:
    """Read the future delivery target from configuration, never a secret."""
    return os.environ.get(
        "TELEMETRY_ENDPOINT", "http://localhost:8000/telemetry/events"
    ).strip()


def record_stub_batch(batch: TelemetryBatch) -> TelemetryReceipt:
    """Record safe verification metadata without logging event properties."""
    event_types = [event.event_type for event in batch.events]
    logger.info(
        "Telemetry batch received count=%d event_types=%s endpoint=%s",
        len(batch.events),
        event_types,
        telemetry_endpoint(),
    )
    return TelemetryReceipt(received=len(batch.events))


@router.post(
    "/events",
    response_model=TelemetryReceipt,
    summary="Validate a telemetry batch (temporary non-persistent stub)",
)
def receive_events(batch: TelemetryBatch) -> TelemetryReceipt:
    return record_stub_batch(batch)
