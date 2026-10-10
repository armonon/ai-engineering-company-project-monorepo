"""Authenticated technical reporting with a bounded, 60-second per-process cache."""

from __future__ import annotations

import time
from collections import OrderedDict
from copy import deepcopy
from datetime import UTC, datetime, timedelta
from threading import Lock
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session
from telemetry import analysis

from database import get_db
from routers.telemetry import _catalogue_events
from security import get_current_user

router = APIRouter(prefix="/telemetry", tags=["telemetry"])
TTL_SECONDS = 60
MAX_CACHE_ENTRIES = 32
_cache: OrderedDict[tuple, tuple[float, dict[str, Any]]] = OrderedDict()
_cache_lock = Lock()


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _parse_date(value: str | None) -> datetime | None:
    if value is None:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed.replace(tzinfo=UTC) if parsed.tzinfo is None else parsed.astimezone(UTC)
    except (ValueError, OverflowError) as exc:
        raise HTTPException(422, "Dates must use ISO 8601 format.") from exc


def clear_report_cache() -> None:
    """Explicit lifecycle/test reset; never flush on every request."""
    with _cache_lock:
        _cache.clear()


@router.get("/report", dependencies=[Depends(get_current_user)])
def report(
    start_date: str | None = Query(None),
    end_date: str | None = Query(None),
    session: Session = Depends(get_db),
) -> dict[str, Any]:
    start, end = _parse_date(start_date), _parse_date(end_date)
    # None is a stable cache key for omitted bounds. A cache hit returns the
    # original resolved period, so rolling defaults are cached too, without lying
    # about which interval generated their data. Equivalent offsets share a key.
    key = (session.get_bind(), start, end)
    with _cache_lock:
        clock = time.monotonic()
        cached = _cache.get(key)
        if cached is not None and clock - cached[0] < TTL_SECONDS:
            _cache.move_to_end(key)
            return deepcopy(cached[1])
        now = _utc_now()
        end = end if end is not None else now
        try:
            start = start if start is not None else end - timedelta(days=7)
        except OverflowError as exc:
            raise HTTPException(422, "Date window is outside the supported range.") from exc
        if start >= end:
            raise HTTPException(422, "start_date must be earlier than end_date.")
        connection = session.connection()
        catalogue = tuple(_catalogue_events())
        result = {
            "period": {"from": start.isoformat(), "to": end.isoformat()},
            "metrics": {
                "events_per_day": analysis.events_per_day(connection, start, end, catalogue),
                "error_rate_by_day": analysis.error_rate_by_day(connection, start, end, catalogue),
                "latency_by_endpoint": analysis.latency_by_endpoint(connection, start, end),
                "auth_failure_rate": analysis.auth_failure_rate(connection, start, end),
            },
        }
        _cache[key] = (time.monotonic(), deepcopy(result))
        _cache.move_to_end(key)
        if len(_cache) > MAX_CACHE_ENTRIES:
            _cache.popitem(last=False)
        return result
