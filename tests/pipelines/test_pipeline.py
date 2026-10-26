"""Isolated unit tests for TrackFlow's pure weekly KPI transformation."""

from __future__ import annotations

from datetime import datetime
from uuid import uuid4

import pytest
from trackflow_process import PipelineQualityError, transform_weekly_performance


def _event(
    event_type: str,
    *,
    quantity: int,
    warehouse: str = "los_angeles",
    client_id: str = "client_01JTF000000000000000000001",
    timestamp: str | datetime = "2026-07-15T12:00:00Z",
) -> dict:
    return {
        "id": str(uuid4()),
        "timestamp": timestamp,
        "event_type": event_type,
        "tags": {
            "event_id": str(uuid4()),
            "warehouse": warehouse,
            "client_id": client_id,
            "product_id": "CLT-SNK-W-42",
            "product_category": "fashion",
            "quantity": quantity,
        },
    }


def test_inbound_units_are_summed_by_warehouse_client_and_week() -> None:
    result = transform_weekly_performance(
        [
            _event("inbound_order_created", quantity=7),
            _event("inbound_order_created", quantity=5),
        ]
    )

    row = result["rows"][0]
    assert row["inbound_units_count"] == 12
    assert row["warehouse"] == "los_angeles"
    assert row["week_start"].isoformat() == "2026-07-13"


def test_hand_calculated_outbound_and_discrepancy_kpis() -> None:
    result = transform_weekly_performance(
        [
            _event("outbound_order_created", quantity=8),
            _event("outbound_order_created", quantity=2),
            _event("outbound_order_created", quantity=4),
            _event("inventory_discrepancy_detected", quantity=1),
            _event("inventory_discrepancy_detected", quantity=2),
        ]
    )

    row = result["rows"][0]
    assert row["outbound_orders_count"] == 3
    assert row["discrepancy_events_count"] == 2
    assert float(row["discrepancy_rate"]) == pytest.approx(2 / 3)


def test_stockout_events_are_counted_not_summed() -> None:
    result = transform_weekly_performance(
        [
            _event("stock_threshold_triggered", quantity=0),
            _event("stock_threshold_triggered", quantity=4),
        ]
    )

    assert result["rows"][0]["stockout_events_count"] == 2


def test_malformed_timestamp_is_rejected_before_any_load() -> None:
    malformed = _event(
        "inbound_order_created",
        quantity=3,
        timestamp=datetime(2026, 7, 15, 12),
    )

    with pytest.raises(PipelineQualityError, match="UTC offset"):
        transform_weekly_performance([malformed])


def test_warehouse_partition_is_preserved() -> None:
    result = transform_weekly_performance(
        [
            _event("inbound_order_created", quantity=9),
            _event("inbound_order_created", quantity=11, warehouse="zaragoza"),
        ]
    )

    assert {
        (row["warehouse"], row["inbound_units_count"])
        for row in result["rows"]
    } == {("los_angeles", 9), ("zaragoza", 11)}
