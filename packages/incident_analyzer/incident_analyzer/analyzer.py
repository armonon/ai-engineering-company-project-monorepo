"""Validation + aggregation logic.

Rules are transcribed directly from CONTEXT-trackflow.md § "Rules for
Invalid Records". Every rule id below is what the console output and
the exported CSV surface by name.

The invalid-record classification is deterministic and single-cause:
a record fails the first rule it hits, in declaration order. This
gives stable counts run to run — the CONTEXT ships expected counts
per rule and expects to see them add up cleanly.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any

CATEGORIES: tuple[str, ...] = (
    "LOST_PARCEL",
    "DELAYED_DELIVERY",
    "WRONG_ADDRESS",
    "RETURN_REQUEST",
    "DAMAGE",
)
STATUSES: tuple[str, ...] = ("OPEN", "CLOSED", "DISCARDED")
COUNTRIES: tuple[str, ...] = ("US", "ES")

CARRIERS_BY_COUNTRY: dict[str, frozenset[str]] = {
    "US": frozenset({"UPS", "FEDEX", "DHL_US"}),
    "ES": frozenset({"MRW", "SEUR", "DHL_ES", "LOCAL_ES"}),
}

REQUIRED_FIELDS: tuple[str, ...] = (
    "incident_id",
    "date",
    "country",
    "customer_type",
    "tracking_number",
    "carrier",
    "category",
    "description",
    "status",
    "customer_email",
)

# --- Rule ids used in the console output + CSV export -----------------------
RULE_MISSING_COUNTRY = "missing_or_invalid_country"
RULE_MISSING_CARRIER_COUNTRY = "carrier_country_mismatch"
RULE_INVALID_TRACKING = "invalid_tracking_number"
RULE_INVALID_CATEGORY = "invalid_or_missing_category"
RULE_EMPTY_DESCRIPTION = "empty_description"
RULE_INVALID_EMAIL = "invalid_or_missing_email"
RULE_CLOSED_NO_SCORE = "closed_without_score"
RULE_SCORE_OUT_OF_RANGE = "score_out_of_range"

RULE_LABELS: dict[str, str] = {
    RULE_MISSING_COUNTRY: "Missing or invalid country",
    RULE_MISSING_CARRIER_COUNTRY: "Carrier/country mismatch",
    RULE_INVALID_TRACKING: "Invalid tracking number",
    RULE_INVALID_CATEGORY: "Invalid or missing category",
    RULE_EMPTY_DESCRIPTION: "Empty description",
    RULE_INVALID_EMAIL: "Invalid or missing email",
    RULE_CLOSED_NO_SCORE: "Closed incident, no score",
    RULE_SCORE_OUT_OF_RANGE: "Satisfaction score out of range",
}

# Declaration order matters — the first failing rule per record wins.
RULE_ORDER: tuple[str, ...] = (
    RULE_MISSING_COUNTRY,
    RULE_MISSING_CARRIER_COUNTRY,
    RULE_INVALID_TRACKING,
    RULE_INVALID_CATEGORY,
    RULE_EMPTY_DESCRIPTION,
    RULE_INVALID_EMAIL,
    RULE_CLOSED_NO_SCORE,
    RULE_SCORE_OUT_OF_RANGE,
)


@dataclass(frozen=True)
class RecordValidation:
    valid: bool
    failed_rule: str | None  # None when valid


@dataclass
class CategoryBreakdown:
    counts: dict[str, int] = field(default_factory=dict)

    def percentage(self, category: str, total: int) -> float:
        return _percent(self.counts.get(category, 0), total)


@dataclass
class StatusBreakdown:
    counts: dict[str, int] = field(default_factory=dict)

    def percentage(self, status: str, total: int) -> float:
        return _percent(self.counts.get(status, 0), total)


@dataclass
class InvalidBreakdown:
    counts: dict[str, int] = field(default_factory=dict)

    def total(self) -> int:
        return sum(self.counts.values())


@dataclass
class SatisfactionSummary:
    scored_count: int = 0
    total_closed: int = 0
    average: float = 0.0
    per_score: dict[int, int] = field(default_factory=dict)


@dataclass
class AnalysisResult:
    total_rows: int
    valid_count: int
    invalid_count: int
    invalid_breakdown: InvalidBreakdown
    category_breakdown: CategoryBreakdown
    status_breakdown: StatusBreakdown
    country_breakdown: dict[str, int]
    satisfaction: SatisfactionSummary


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def validate_record(row: dict[str, Any]) -> RecordValidation:
    """Return the first failing rule (declaration-order) or None."""
    country = _clean(row.get("country"))
    if country not in COUNTRIES:
        return RecordValidation(False, RULE_MISSING_COUNTRY)

    carrier = _clean(row.get("carrier"))
    if not carrier or carrier not in CARRIERS_BY_COUNTRY.get(country, frozenset()):
        return RecordValidation(False, RULE_MISSING_CARRIER_COUNTRY)

    tracking = _clean(row.get("tracking_number"))
    if not tracking or len(tracking) < 8:
        return RecordValidation(False, RULE_INVALID_TRACKING)

    category = _clean(row.get("category"))
    if category not in CATEGORIES:
        return RecordValidation(False, RULE_INVALID_CATEGORY)

    description = _clean(row.get("description"))
    if not description or len(description) < 5:
        return RecordValidation(False, RULE_EMPTY_DESCRIPTION)

    email = _clean(row.get("customer_email"))
    if not email or "@" not in email:
        return RecordValidation(False, RULE_INVALID_EMAIL)

    status = _clean(row.get("status"))
    raw_score = _clean(row.get("satisfaction_score"))
    if status == "CLOSED" and not raw_score:
        return RecordValidation(False, RULE_CLOSED_NO_SCORE)
    if raw_score:
        try:
            score = int(raw_score)
        except ValueError:
            return RecordValidation(False, RULE_SCORE_OUT_OF_RANGE)
        if score < 1 or score > 5:
            return RecordValidation(False, RULE_SCORE_OUT_OF_RANGE)

    return RecordValidation(True, None)


# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------


def analyse(rows: Iterable[dict[str, Any]]) -> AnalysisResult:
    rows = list(rows)
    invalid = InvalidBreakdown(counts={rule: 0 for rule in RULE_ORDER})
    category = CategoryBreakdown(counts={c: 0 for c in CATEGORIES})
    status = StatusBreakdown(counts={s: 0 for s in STATUSES})
    country: dict[str, int] = {c: 0 for c in COUNTRIES}
    per_score: dict[int, int] = {s: 0 for s in range(1, 6)}
    closed_count = 0
    scored_sum = 0
    scored_count = 0
    valid_count = 0

    for row in rows:
        verdict = validate_record(row)
        if not verdict.valid:
            assert verdict.failed_rule is not None
            invalid.counts[verdict.failed_rule] += 1
            continue

        valid_count += 1
        category.counts[_clean(row["category"])] += 1
        status.counts[_clean(row["status"])] += 1
        country[_clean(row["country"])] += 1

        if _clean(row["status"]) == "CLOSED":
            closed_count += 1
            score = int(_clean(row["satisfaction_score"]))
            per_score[score] += 1
            scored_sum += score
            scored_count += 1

    average = round(scored_sum / scored_count, 2) if scored_count else 0.0

    return AnalysisResult(
        total_rows=len(rows),
        valid_count=valid_count,
        invalid_count=len(rows) - valid_count,
        invalid_breakdown=invalid,
        category_breakdown=category,
        status_breakdown=status,
        country_breakdown=country,
        satisfaction=SatisfactionSummary(
            scored_count=scored_count,
            total_closed=closed_count,
            average=average,
            per_score=per_score,
        ),
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _clean(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _percent(part: int, whole: int) -> float:
    if whole <= 0:
        return 0.0
    return round((part / whole) * 100, 1)
