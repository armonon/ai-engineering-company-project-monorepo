"""Tests locking the CONTEXT.md expected values against the shipped
sample CSV. If any number changes, either the CSV was regenerated
or a rule drifted — either way the test should fail loud."""

from __future__ import annotations

from pathlib import Path

from incident_analyzer import (
    analyse,
    read_csv,
    render_console,
    result_to_csv_rows,
    validate_record,
)
from incident_analyzer.analyzer import (
    RULE_CLOSED_NO_SCORE,
    RULE_INVALID_CATEGORY,
    RULE_INVALID_EMAIL,
    RULE_INVALID_TRACKING,
    RULE_MISSING_CARRIER_COUNTRY,
)

# scripts/incidents-trackflow.csv lives two levels up from tests/
FIXTURE = Path(__file__).resolve().parents[3] / "scripts" / "incidents-trackflow.csv"


def _load() -> list[dict]:
    return read_csv(FIXTURE)


def test_totals_match_context() -> None:
    result = analyse(_load())
    assert result.total_rows == 100
    assert result.valid_count == 95
    assert result.invalid_count == 5


def test_invalid_breakdown_matches_context() -> None:
    result = analyse(_load())
    counts = result.invalid_breakdown.counts
    assert counts[RULE_INVALID_TRACKING] == 1
    assert counts[RULE_MISSING_CARRIER_COUNTRY] == 1
    assert counts[RULE_INVALID_CATEGORY] == 1
    assert counts[RULE_INVALID_EMAIL] == 1
    assert counts[RULE_CLOSED_NO_SCORE] == 1


def test_category_counts_match_context() -> None:
    result = analyse(_load())
    assert result.category_breakdown.counts == {
        "LOST_PARCEL": 14,
        "DELAYED_DELIVERY": 38,
        "WRONG_ADDRESS": 19,
        "RETURN_REQUEST": 17,
        "DAMAGE": 7,
    }


def test_status_counts_match_context() -> None:
    result = analyse(_load())
    assert result.status_breakdown.counts == {
        "OPEN": 29,
        "CLOSED": 52,
        "DISCARDED": 14,
    }


def test_country_counts_match_context() -> None:
    result = analyse(_load())
    assert result.country_breakdown == {"US": 50, "ES": 45}


def test_satisfaction_matches_context() -> None:
    result = analyse(_load())
    sat = result.satisfaction
    assert sat.total_closed == 52
    assert sat.scored_count == 52
    assert sat.average == 3.06
    assert sat.per_score == {1: 6, 2: 11, 3: 15, 4: 14, 5: 6}


def test_console_never_leaks_email() -> None:
    result = analyse(_load())
    rendered = render_console(result, "incidents-trackflow.csv")
    assert "@" not in rendered  # rule from CONTEXT.md


def test_csv_export_never_leaks_email() -> None:
    result = analyse(_load())
    rows = result_to_csv_rows(result)
    for row in rows:
        for value in row.values():
            assert "@" not in value


def test_validate_record_happy_path() -> None:
    row = {
        "incident_id": "TRF-000042",
        "date": "2024-01-08",
        "country": "ES",
        "customer_type": "B2C",
        "tracking_number": "ABCDEFGH12345",
        "carrier": "MRW",
        "category": "RETURN_REQUEST",
        "description": "Valid description here",
        "status": "CLOSED",
        "customer_email": "test@example.com",
        "satisfaction_score": "3",
    }
    assert validate_record(row).valid is True


def test_validate_record_carrier_country_mismatch() -> None:
    row = {
        "country": "ES",
        "carrier": "UPS",  # US-only
        "tracking_number": "ABCDEFGH12345",
        "category": "DAMAGE",
        "description": "irrelevant text",
        "status": "OPEN",
        "customer_email": "a@b.com",
    }
    v = validate_record(row)
    assert v.valid is False
    assert v.failed_rule == RULE_MISSING_CARRIER_COUNTRY
