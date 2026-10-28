from __future__ import annotations

import httpx
import pytest
from company_tools_mcp.upstream import CompanyAPI
from mcp.server.fastmcp.exceptions import ToolError


def response(status: int, payload: dict | list) -> httpx.Response:
    return httpx.Response(status, json=payload, request=httpx.Request("GET", "https://api"))


def test_incident_methods_use_exact_manager_routes_and_bearer_token(monkeypatch):
    calls = []

    def request(method, url, **kwargs):
        calls.append((method, url, kwargs))
        return response(200 if method != "POST" else 201, {"id": 482, "status": "open"})

    monkeypatch.setattr(httpx, "request", request)
    api = CompanyAPI("https://api.example.test", "service-token", 4.0)

    api.get_incident(482)
    api.create_incident({"title": "Missing", "category": "lost_parcel"})
    api.update_incident_status(482, "in_progress")

    assert [(method, url) for method, url, _ in calls] == [
        ("GET", "https://api.example.test/api/incidents/482"),
        ("POST", "https://api.example.test/api/incidents"),
        ("PATCH", "https://api.example.test/api/incidents/482/status"),
    ]
    assert calls[-1][2]["json"] == {"status": "in_progress"}
    assert all(call[2]["headers"] == {"Authorization": "Bearer service-token"} for call in calls)
    assert all(call[2]["timeout"] == 4.0 for call in calls)


@pytest.mark.parametrize(
    ("status", "code"),
    [
        (400, "VALIDATION_ERROR"),
        (401, "UPSTREAM_AUTH_FAILED"),
        (403, "UPSTREAM_FORBIDDEN"),
        (404, "UPSTREAM_NOT_FOUND"),
        (503, "UPSTREAM_UNAVAILABLE"),
    ],
)
def test_upstream_failures_have_distinct_safe_codes(monkeypatch, status, code):
    monkeypatch.setattr(
        httpx,
        "request",
        lambda *_args, **_kwargs: response(status, {"detail": "rejected"}),
    )
    api = CompanyAPI("https://api.example.test", "service-token")
    with pytest.raises(ToolError, match=code):
        api.get_incident(482)
