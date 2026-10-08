"""Console renderer — matches the exact shape shown in CONTEXT.md
§ 'Expected Output'.

Kept pure (returns a string) so it can be unit-tested and reused
from the API's health/debug path if we ever want a preview endpoint.
Contains no I/O. `scripts/analyze.py` is the one that prints.
"""

from __future__ import annotations

from .analyzer import (
    CATEGORIES,
    COUNTRIES,
    RULE_LABELS,
    RULE_ORDER,
    STATUSES,
    AnalysisResult,
)

_DIVIDER = "=" * 60

_SATISFACTION_LABELS = {
    1: "Very dissatisfied",
    2: "Dissatisfied",
    3: "Neutral",
    4: "Satisfied",
    5: "Very satisfied",
}


def render_console(result: AnalysisResult, source_filename: str) -> str:
    lines: list[str] = []
    add = lines.append

    add(_DIVIDER)
    add("  TRACKFLOW — INCIDENT REPORT ANALYSIS")
    add(f"  Source file: {source_filename}")
    add(_DIVIDER)
    add("")
    add(f"TOTAL RECORDS IN FILE {'.' * 10} {result.total_rows}")
    add(f"  ├─ Valid records {'.' * 15} {result.valid_count}")
    add(f"  └─ Invalid / incomplete {'.' * 10} {result.invalid_count}")
    add("")

    add("INVALID RECORDS BREAKDOWN")
    invalid_present = [rule for rule in RULE_ORDER if result.invalid_breakdown.counts.get(rule, 0)]
    for i, rule in enumerate(invalid_present):
        prefix = "└" if i == len(invalid_present) - 1 else "├"
        label = RULE_LABELS[rule]
        add(f"  {prefix}─ {label.ljust(35, '.')} {result.invalid_breakdown.counts[rule]}")
    if not invalid_present:
        add("  └─ No invalid records.")
    add("")

    valid_total = result.valid_count

    add("BREAKDOWN BY CATEGORY (valid records)")
    for i, category in enumerate(CATEGORIES):
        count = result.category_breakdown.counts.get(category, 0)
        prefix = "└" if i == len(CATEGORIES) - 1 else "├"
        pct = _fmt_pct(count, valid_total)
        add(f"  {prefix}─ {category.ljust(20, '.')} {count:>3}  ({pct})")
    add("")

    add("BREAKDOWN BY STATUS (valid records)")
    for i, status in enumerate(STATUSES):
        count = result.status_breakdown.counts.get(status, 0)
        prefix = "└" if i == len(STATUSES) - 1 else "├"
        pct = _fmt_pct(count, valid_total)
        add(f"  {prefix}─ {status.ljust(20, '.')} {count:>3}  ({pct})")
    add("")

    add("BREAKDOWN BY COUNTRY (valid records) — recommended, not required")
    for i, country in enumerate(COUNTRIES):
        count = result.country_breakdown.get(country, 0)
        prefix = "└" if i == len(COUNTRIES) - 1 else "├"
        pct = _fmt_pct(count, valid_total)
        add(f"  {prefix}─ {country.ljust(20, '.')} {count:>3}  ({pct})")
    add("")

    sat = result.satisfaction
    add("SATISFACTION INDEX (closed incidents)")
    add(f"  Scored incidents: {sat.scored_count} of {sat.total_closed}")
    add(f"  Average score: {sat.average:.2f} / 5.00")
    for score in range(1, 6):
        count = sat.per_score.get(score, 0)
        prefix = "└" if score == 5 else "├"
        label = f"Score {score} ({_SATISFACTION_LABELS[score]})"
        add(f"  {prefix}─ {label.ljust(30, '.')} {count}")
    add("")

    add(_DIVIDER)
    return "\n".join(lines)


def _fmt_pct(part: int, whole: int) -> str:
    if whole <= 0:
        return "0.0%"
    return f"{(part / whole) * 100:.1f}%"
