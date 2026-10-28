"""Small HTTP boundary for the existing TrackFlow APIs."""

from __future__ import annotations

from typing import Any

import httpx
from mcp.server.fastmcp.exceptions import ToolError


class CompanyAPI:
    def __init__(self, base_url: str, token: str, timeout_seconds: float = 4.0):
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.timeout_seconds = timeout_seconds

    def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        try:
            response = httpx.request(
                method,
                f"{self.base_url}{path}",
                headers={"Authorization": f"Bearer {self.token}"},
                timeout=self.timeout_seconds,
                **kwargs,
            )
        except (httpx.TimeoutException, httpx.NetworkError) as exc:
            raise ToolError("UPSTREAM_UNAVAILABLE: the TrackFlow API could not be reached") from exc
        if response.status_code == 401:
            raise ToolError("UPSTREAM_AUTH_FAILED: company service token was rejected")
        if response.status_code == 403:
            raise ToolError("UPSTREAM_FORBIDDEN: company service token lacks permission")
        if response.status_code == 404:
            raise ToolError("UPSTREAM_NOT_FOUND: the requested company record does not exist")
        if response.status_code in {400, 409, 422}:
            detail = response.json().get("detail", "request rejected")
            raise ToolError(f"VALIDATION_ERROR: {detail}")
        if response.status_code >= 500:
            raise ToolError("UPSTREAM_UNAVAILABLE: TrackFlow API returned a server error")
        response.raise_for_status()
        return response.json()

    def get_incident(self, ticket_id: int) -> dict[str, Any]:
        return self._request("GET", f"/api/incidents/{ticket_id}")

    def create_incident(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request("POST", "/api/incidents", json=payload)

    def update_incident_status(self, ticket_id: int, status: str) -> dict[str, Any]:
        return self._request("PATCH", f"/api/incidents/{ticket_id}/status", json={"status": status})

    def list_inventory(self, warehouse: str | None = None) -> list[dict[str, Any]]:
        params = {"warehouse": warehouse} if warehouse else None
        return self._request("GET", "/inventory/products", params=params)
