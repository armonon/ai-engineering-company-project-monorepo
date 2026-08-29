"""Incident-analysis endpoints (Milestone: Incident Analyser).

Analysis + validation is imported wholesale from `incident_analyzer`
(packages/incident_analyzer). This service does NOT re-implement any
rule — see docs/ARCHITECTURE_PROPOSAL.md § MONO-1.
"""

from __future__ import annotations

import csv
from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import Response
from incident_analyzer import AnalysisResult, analyse
from incident_analyzer.analyzer import RULE_LABELS
from incident_analyzer.csv_io import (
    read_csv_bytes,
    result_to_csv_rows,
    write_csv_bytes,
)

from models import UserInDB
from security import get_current_user

router = APIRouter(prefix="/api/incidents", tags=["incidents"])

# In-memory cache of the most recent analysis — used by /export.
# Not persistent by design; the exercise doesn't ask for a DB here.
_LAST_RESULT: AnalysisResult | None = None


def _serialize(result: AnalysisResult) -> dict[str, Any]:
    """Frontend-friendly JSON representation of the analysis."""
    return {
        "totals": {
            "total_rows": result.total_rows,
            "valid_records": result.valid_count,
            "invalid_records": result.invalid_count,
        },
        "invalid_breakdown": [
            {"rule": rule, "label": RULE_LABELS[rule], "count": count}
            for rule, count in result.invalid_breakdown.counts.items()
        ],
        "category_breakdown": result.category_breakdown.counts,
        "status_breakdown": result.status_breakdown.counts,
        "country_breakdown": result.country_breakdown,
        "satisfaction": {
            "scored_incidents": result.satisfaction.scored_count,
            "closed_incidents": result.satisfaction.total_closed,
            "average_score": result.satisfaction.average,
            "per_score": result.satisfaction.per_score,
        },
    }


@router.post("/analyze", summary="Analyse an incidents CSV upload")
async def analyze_incidents(
    file: UploadFile = File(...),
    _caller: UserInDB = Depends(get_current_user),
) -> dict[str, Any]:
    """Accept a multipart CSV upload, validate + analyse, cache the
    result for a later /export call, and return the summary as JSON."""
    global _LAST_RESULT

    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Upload must be a .csv file.",
        )

    payload = await file.read()
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty.",
        )

    # Decoding and parsing fail in different ways and need different
    # advice, so they are caught separately rather than under one
    # `except Exception`. The exception text itself is never forwarded —
    # it carries byte offsets and codec internals that mean nothing to
    # the person who uploaded the file.
    try:
        rows = read_csv_bytes(payload)
    except UnicodeDecodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "This file isn't UTF-8 text. Re-export it as CSV UTF-8 "
                "from your spreadsheet tool and upload it again."
            ),
        ) from exc
    except csv.Error as exc:
        # Reachable: the csv module refuses fields over 128 KB, and also
        # raises here on embedded NUL bytes and broken quoting. Before
        # this existed it escaped as a 500 with a plain-text body.
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "This file isn't readable as CSV — a row may be malformed "
                "or a single field may be unusually large. Check the export "
                "and try again."
            ),
        ) from exc

    if not rows:
        raise HTTPException(
            # 422 — the constant was renamed in Starlette; use the literal
            # so this keeps working across both naming eras.
            status_code=422,
            detail="CSV had a header but no data rows.",
        )

    try:
        result = analyse(rows)
    except (ValueError, TypeError, KeyError) as exc:
        # The analyser expects the documented column set. Shaped-wrong
        # data is the uploader's problem to fix, so it gets a 422 that
        # says so rather than an anonymous 500.
        raise HTTPException(
            status_code=422,
            detail=(
                "The file was read, but its columns don't match the expected "
                "incident export. Compare it against the sample CSV and try again."
            ),
        ) from exc
    _LAST_RESULT = result
    return _serialize(result)


@router.get(
    "/results/export",
    summary="Download the last analysis as a CSV (one row per metric)",
)
def export_last_results(
    _caller: UserInDB = Depends(get_current_user),
) -> Response:
    if _LAST_RESULT is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No analysis has been run yet — POST /api/incidents/analyze first.",
        )
    body = write_csv_bytes(result_to_csv_rows(_LAST_RESULT))
    return Response(
        content=body,
        media_type="text/csv",
        headers={
            "Content-Disposition": 'attachment; filename="trackflow-incidents-results.csv"'
        },
    )
