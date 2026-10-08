"""CSV reader (path or file-like) + result-to-CSV serializer.

The result-to-CSV serializer emits ONE row per metric, per the
stakeholder note in CONTEXT.md ("The CSV export should have one row
per metric — I'll use it in the client report").

Emails are never included in the output — the exported CSV has
metric names and numeric values only.
"""

from __future__ import annotations

import csv
import io
from collections.abc import Iterable
from pathlib import Path
from typing import IO

from .analyzer import (
    RULE_LABELS,
    RULE_ORDER,
    AnalysisResult,
)


def read_csv(source: str | Path | IO[str]) -> list[dict]:
    """Read a CSV into a list of row dicts.

    Accepts a file path, a Path, or an already-opened text stream —
    lets the API pass an in-memory stream without writing a temp file.
    """
    if hasattr(source, "read"):
        return list(csv.DictReader(source))
    path = Path(source)
    with path.open("r", encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def read_csv_bytes(data: bytes) -> list[dict]:
    """Read a CSV out of a bytes payload (multipart upload path)."""
    text = data.decode("utf-8-sig")  # strip BOM if present
    return read_csv(io.StringIO(text))


def result_to_csv_rows(result: AnalysisResult) -> list[dict[str, str]]:
    """One row per metric — the shape Valentina asked for.

    Columns are (metric, category, value). Values are strings so
    the DictWriter round-trip is stable and the file opens cleanly
    in Excel / Sheets without number-format surprises.
    """
    rows: list[dict[str, str]] = []

    def add(metric: str, category: str, value) -> None:
        rows.append({"metric": metric, "category": category, "value": _stringify(value)})

    add("totals", "total_rows", result.total_rows)
    add("totals", "valid_records", result.valid_count)
    add("totals", "invalid_records", result.invalid_count)

    for rule in RULE_ORDER:
        add("invalid_breakdown", RULE_LABELS[rule], result.invalid_breakdown.counts.get(rule, 0))

    for category, count in result.category_breakdown.counts.items():
        add("category_breakdown", category, count)

    for status, count in result.status_breakdown.counts.items():
        add("status_breakdown", status, count)

    for country, count in result.country_breakdown.items():
        add("country_breakdown", country, count)

    add(
        "satisfaction",
        "scored_incidents",
        result.satisfaction.scored_count,
    )
    add(
        "satisfaction",
        "closed_incidents",
        result.satisfaction.total_closed,
    )
    add("satisfaction", "average_score", result.satisfaction.average)
    for score in sorted(result.satisfaction.per_score.keys()):
        add(
            "satisfaction",
            f"score_{score}",
            result.satisfaction.per_score[score],
        )

    return rows


def write_csv_bytes(rows: Iterable[dict[str, str]]) -> bytes:
    """Serialize the metric rows to a UTF-8 CSV byte string."""
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=["metric", "category", "value"])
    writer.writeheader()
    for row in rows:
        writer.writerow(row)
    return buf.getvalue().encode("utf-8")


def _stringify(value) -> str:
    if isinstance(value, float):
        # 2-decimal precision matches the console output; safe for CSV.
        return f"{value:.2f}"
    return str(value)
