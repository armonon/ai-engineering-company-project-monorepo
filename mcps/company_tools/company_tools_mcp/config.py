"""Environment-only configuration for the company-tools MCP resource server."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    resource_url: str
    issuer_url: str
    company_api_url: str
    company_api_token: str
    audit_log_path: Path
    request_timeout_seconds: float = 4.0

    @classmethod
    def from_env(cls) -> Settings:
        required = {
            "MCP_RESOURCE_URL": os.getenv("MCP_RESOURCE_URL", "").strip(),
            "MCP_AUTH_ISSUER": os.getenv("MCP_AUTH_ISSUER", "").strip(),
            "COMPANY_API_URL": os.getenv("COMPANY_API_URL", "").strip(),
            "COMPANY_API_TOKEN": os.getenv("COMPANY_API_TOKEN", "").strip(),
        }
        missing = [name for name, value in required.items() if not value]
        if missing:
            names = ", ".join(sorted(missing))
            raise RuntimeError(f"Missing required company-tools MCP settings: {names}")
        timeout = float(os.getenv("MCP_UPSTREAM_TIMEOUT_SECONDS", "4.0"))
        if timeout <= 0:
            raise RuntimeError("MCP_UPSTREAM_TIMEOUT_SECONDS must be greater than zero")
        return cls(
            resource_url=required["MCP_RESOURCE_URL"].rstrip("/"),
            issuer_url=required["MCP_AUTH_ISSUER"].rstrip("/"),
            company_api_url=required["COMPANY_API_URL"].rstrip("/"),
            company_api_token=required["COMPANY_API_TOKEN"],
            audit_log_path=Path(os.getenv("MCP_AUDIT_LOG", "data/company_tools_audit.jsonl")),
            request_timeout_seconds=timeout,
        )
