"""Append-only, secret-free audit log for MCP tool invocations."""

from __future__ import annotations

import json
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


class AuditLogger:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def record(
        self,
        *,
        client_id: str,
        subject: str,
        tool: str,
        result: str,
        target_id: int | str | None = None,
    ) -> None:
        event: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "client_id": client_id,
            "subject": subject,
            "tool": tool,
            "result": result,
        }
        if target_id is not None:
            event["target_id"] = target_id
        with self._lock:
            with self.path.open("a", encoding="utf-8") as stream:
                stream.write(json.dumps(event, sort_keys=True) + "\n")
