"""Persistent, queryable traces for TrackFlow agent runs."""

from __future__ import annotations

import json
import os
import sqlite3
import threading
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


class TraceStore:
    """Append-only SQLite trace events, one ordered stream per graph run."""

    def __init__(self, path: str | Path | None = None) -> None:
        default_path = Path(__file__).resolve().parents[1] / "api" / "data" / "agent_traces.db"
        configured = path or os.getenv("AGENT_TRACE_DB") or default_path
        self.path = Path(configured)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._ensure_schema()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=10)
        connection.row_factory = sqlite3.Row
        return connection

    def _ensure_schema(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS agent_trace_events (
                    run_id TEXT NOT NULL,
                    sequence INTEGER NOT NULL,
                    node TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    output_json TEXT NOT NULL,
                    PRIMARY KEY (run_id, sequence)
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS agent_trace_runs (
                    run_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL
                )
                """
            )

    def register_run(self, run_id: str, user_id: str) -> None:
        with self._lock, self._connect() as connection:
            connection.execute(
                "INSERT OR IGNORE INTO agent_trace_runs (run_id, user_id) VALUES (?, ?)",
                (run_id, user_id),
            )

    def is_owner(self, run_id: str, user_id: str) -> bool:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT 1 FROM agent_trace_runs WHERE run_id = ? AND user_id = ?",
                (run_id, user_id),
            ).fetchone()
        return row is not None

    def append(self, run_id: str, node: str, output: dict[str, Any]) -> None:
        """Append one sanitised node result without overwriting history."""
        with self._lock, self._connect() as connection:
            row = connection.execute(
                "SELECT COALESCE(MAX(sequence), 0) + 1 FROM agent_trace_events WHERE run_id = ?",
                (run_id,),
            ).fetchone()
            sequence = int(row[0])
            connection.execute(
                """
                INSERT INTO agent_trace_events
                    (run_id, sequence, node, created_at, output_json)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    sequence,
                    node,
                    datetime.now(UTC).isoformat(),
                    json.dumps(output, sort_keys=True),
                ),
            )

    def get(self, run_id: str) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT sequence, node, created_at, output_json
                FROM agent_trace_events
                WHERE run_id = ?
                ORDER BY sequence
                """,
                (run_id,),
            ).fetchall()
        return [
            {
                "sequence": int(row["sequence"]),
                "node": row["node"],
                "created_at": row["created_at"],
                "output": json.loads(row["output_json"]),
            }
            for row in rows
        ]

    def guardrail_summary(self) -> dict[str, dict[str, int] | int]:
        """Aggregate persisted block/redirect events without exposing prompts."""
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT output_json FROM agent_trace_events WHERE node = 'guardrail'"
            ).fetchall()
        events = [json.loads(row["output_json"]) for row in rows]
        return {
            "total": len(events),
            "by_failure_type": dict(
                Counter(str(event.get("failure_type") or "unknown") for event in events)
            ),
            "by_action": dict(Counter(str(event.get("action") or "unknown") for event in events)),
            "by_reason": dict(Counter(str(event.get("reason") or "unknown") for event in events)),
        }
