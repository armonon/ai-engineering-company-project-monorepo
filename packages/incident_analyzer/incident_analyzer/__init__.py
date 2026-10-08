"""TrackFlow incident-report CSV analyser.

Public API:
    - analyse(rows) -> AnalysisResult
    - read_csv(path_or_file) -> list[dict]
    - render_console(result) -> str        (readable console output)
    - result_to_csv_rows(result) -> list[dict]  (one row per metric)

Every code path in this package must obey the CONTEXT.md rule:
    "Your script must never print, log, or export individual email
     addresses in any output."
Any function that would emit a customer_email violates the contract
and MUST be removed. Nothing exported below does that.
"""

from .analyzer import (
    AnalysisResult,
    CategoryBreakdown,
    InvalidBreakdown,
    RecordValidation,
    SatisfactionSummary,
    StatusBreakdown,
    analyse,
    validate_record,
)
from .console import render_console
from .csv_io import read_csv, result_to_csv_rows

__all__ = [
    "AnalysisResult",
    "CategoryBreakdown",
    "InvalidBreakdown",
    "RecordValidation",
    "SatisfactionSummary",
    "StatusBreakdown",
    "analyse",
    "read_csv",
    "render_console",
    "result_to_csv_rows",
    "validate_record",
]
