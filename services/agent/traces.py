"""Persistent, queryable traces for TrackFlow agent runs."""

from __future__ import annotations

import json
import os
import sqlite3
import threading
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
