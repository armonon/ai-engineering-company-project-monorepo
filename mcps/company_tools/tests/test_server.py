from __future__ import annotations

import json
import socket
import threading
import time
from pathlib import Path
from typing import Any

import pytest
import uvicorn
from company_tools_mcp.config import Settings
from company_tools_mcp.server import ALL_SCOPES, create_server
from langchain_mcp_adapters.client import MultiServerMCPClient
from mcp.server.fastmcp.exceptions import ToolError
from mcpauth.config import (
    AuthorizationServerMetadata,
    AuthServerConfig,
    AuthServerType,
)
from mcpauth.types import AuthInfo
from starlette.testclient import TestClient


class FakeCompanyAPI:
    def __init__(self) -> None:
        self.calls: list[tuple[Any, ...]] = []

    def get_incident(self, ticket_id: int) -> dict[str, Any]:
        self.calls.append(("get", ticket_id))
        return {
            "id": ticket_id,
            "status": "in_progress",
            "category": "lost_parcel",
            "origin": "customer",
            "branch": "central",
        }

    def create_incident(self, payload: dict[str, Any]) -> dict[str, Any]:
        self.calls.append(("create", payload))
        return {"id": 9, "status": "open", **payload}

    def update_incident_status(self, ticket_id: int, status: str) -> dict[str, Any]:
        self.calls.append(("update", ticket_id, status))
        return {
            "id": ticket_id,
            "status": status,
            "category": "lost_parcel",
            "origin": "branch",
            "branch": "zaragoza_warehouse",
        }

    def list_inventory(self, warehouse: str | None = None) -> list[dict[str, Any]]:
        self.calls.append(("inventory", warehouse))
        return [
            {
                "id": 4,
                "name": "USB-C Fast Charger 65W",
                "sku": "TEC-CHG-065",
                "warehouse": "ZGZ",
                "current_stock": 31,
            }
        ]


def auth_server() -> AuthServerConfig:
    return AuthServerConfig(
        type=AuthServerType.OIDC,
        metadata=AuthorizationServerMetadata(
            issuer="https://auth.example.test",
            authorization_endpoint="https://auth.example.test/authorize",
            token_endpoint="https://auth.example.test/token",
            jwks_uri="https://auth.example.test/jwks.json",
            response_types_supported=["code"],
            scopes_supported=ALL_SCOPES,
        ),
    )


def verifier(token: str) -> AuthInfo:
    scopes = ALL_SCOPES if token == "full-token" else ["incidents:read"]
    return AuthInfo(
        token=token,
        issuer="https://auth.example.test",
        client_id="playground-client",
        scopes=scopes,
        subject="operator-7",
        audience="https://mcp.example.test/mcp",
        claims={},
    )


@pytest.fixture
def built(tmp_path: Path):
    settings = Settings(
        resource_url="https://mcp.example.test/mcp",
        issuer_url="https://auth.example.test",
        company_api_url="https://api.example.test",
        company_api_token="test-only-upstream-token",
        audit_log_path=tmp_path / "audit.jsonl",
    )
    upstream = FakeCompanyAPI()
    bundle = create_server(
        settings,
        company_api=upstream,
        auth_server=auth_server(),
        verify_access_token=verifier,
    )
    return bundle, upstream, settings


def set_auth(bundle, scopes: list[str]) -> None:
    bundle.auth._context_var.set(
        AuthInfo(
            token="not-logged",
            issuer="https://auth.example.test",
            client_id="test-client",
            scopes=scopes,
            subject="operator-7",
            audience="https://mcp.example.test/mcp",
            claims={},
        )
    )


def structured(result):
    """FastMCP returns (content blocks, structured content) for typed tools."""
    return result[1]


def test_unauthenticated_mcp_request_is_401_with_discovery_hint(built):
    bundle, _, _ = built
    with TestClient(bundle.app) as client:
        response = client.post("/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
    assert response.status_code == 401
    assert "resource_metadata" in response.headers["www-authenticate"]


def test_protected_resource_metadata_is_public_and_complete(built):
    bundle, _, _ = built
    with TestClient(bundle.app) as client:
        response = client.get("/.well-known/oauth-protected-resource/mcp")
    assert response.status_code == 200
    assert response.json() == {
        "resource": "https://mcp.example.test/mcp",
        "scopes_supported": ALL_SCOPES,
        "bearer_methods_supported": ["header"],
        "resource_name": "TrackFlow company tools",
        "resource_documentation": "https://mcp.example.test/mcp/docs",
        "authorization_servers": ["https://auth.example.test"],
    }


@pytest.mark.asyncio
async def test_discovery_explains_tools_and_permissions(built):
    bundle, _, _ = built
    tools = {tool.name: tool for tool in await bundle.mcp.list_tools()}
    assert set(tools) == {
        "get_incident",
        "create_incident",
        "update_incident_status",
        "query_inventory",
        "attempt_inventory_write",
    }
    assert "Requires incidents:read" in tools["get_incident"].description
    assert tools["get_incident"].annotations.readOnlyHint is True
    assert tools["query_inventory"].annotations.readOnlyHint is True
    assert tools["attempt_inventory_write"].annotations.destructiveHint is True
    assert "ticket_id" in tools["get_incident"].inputSchema["properties"]
    assert "status" in tools["get_incident"].outputSchema["properties"]
    assert "products" in tools["query_inventory"].outputSchema["properties"]


@pytest.mark.asyncio
async def test_incident_and_inventory_tools_use_real_upstream_boundary(built):
    bundle, upstream, settings = built
    set_auth(bundle, ALL_SCOPES)
    incident = structured(await bundle.mcp.call_tool("get_incident", {"ticket_id": 482}))
    inventory = structured(
        await bundle.mcp.call_tool("query_inventory", {"query": "TEC-CHG-065", "warehouse": "ZGZ"})
    )
    assert incident["status"] == "in_progress"
    assert inventory["count"] == 1
    assert upstream.calls == [("get", 482), ("inventory", "ZGZ")]
    events = [json.loads(line) for line in settings.audit_log_path.read_text().splitlines()]
    assert [(event["tool"], event["result"]) for event in events] == [
        ("get_incident", "success"),
        ("query_inventory", "success"),
    ]
    assert all("token" not in event for event in events)


@pytest.mark.asyncio
async def test_incident_writes_use_lifecycle_tool_and_write_scope(built):
    bundle, upstream, _ = built
    set_auth(bundle, ALL_SCOPES)
    created = structured(
        await bundle.mcp.call_tool(
            "create_incident",
            {
                "title": "Parcel missing",
                "description": "Not present at loading bay",
                "category": "lost_parcel",
                "origin": "branch",
                "branch": "zaragoza_warehouse",
            },
        )
    )
    updated = structured(
        await bundle.mcp.call_tool(
            "update_incident_status",
            {"ticket_id": created["id"], "status": "in_progress"},
        )
    )
    assert updated["id"] == 9
    assert updated["status"] == "in_progress"
    assert upstream.calls[-1] == ("update", 9, "in_progress")

    set_auth(bundle, ["incidents:read"])
    with pytest.raises(ToolError, match="AUTH_SCOPE_MISSING"):
        await bundle.mcp.call_tool("update_incident_status", {"ticket_id": 9, "status": "resolved"})


@pytest.mark.asyncio
async def test_inventory_write_is_explicitly_rejected_and_audited(built):
    bundle, upstream, settings = built
    set_auth(bundle, ["inventory:read"])
    with pytest.raises(ToolError, match="INVENTORY_READ_ONLY"):
        await bundle.mcp.call_tool(
            "attempt_inventory_write",
            {"operation": "delete", "target": "TEC-CHG-065"},
        )
    assert upstream.calls == []
    event = json.loads(settings.audit_log_path.read_text().splitlines()[-1])
    assert event["tool"] == "attempt_inventory_write"
    assert event["result"] == "INVENTORY_READ_ONLY"


@pytest.mark.asyncio
async def test_oauth_http_discovery_and_invocation_through_langchain_adapter(tmp_path):
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
    resource_url = f"http://127.0.0.1:{port}/mcp"

    def local_verifier(token: str) -> AuthInfo:
        assert token == "full-token"
        return AuthInfo(
            token=token,
            issuer="https://auth.example.test",
            client_id="adapter-client",
            scopes=ALL_SCOPES,
            subject="operator-7",
            audience=resource_url,
            claims={},
        )

    settings = Settings(
        resource_url=resource_url,
        issuer_url="https://auth.example.test",
        company_api_url="https://api.example.test",
        company_api_token="test-only-upstream-token",
        audit_log_path=tmp_path / "adapter-audit.jsonl",
    )
    upstream = FakeCompanyAPI()
    bundle = create_server(
        settings,
        company_api=upstream,
        auth_server=auth_server(),
        verify_access_token=local_verifier,
    )
    server = uvicorn.Server(
        uvicorn.Config(bundle.app, host="127.0.0.1", port=port, log_level="error")
    )
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    for _ in range(100):
        if server.started:
            break
        time.sleep(0.01)
    assert server.started

    try:
        client = MultiServerMCPClient(
            {
                "company_tools": {
                    "transport": "streamable_http",
                    "url": resource_url,
                    "headers": {"Authorization": "Bearer full-token"},
                }
            }
        )
        tools = await client.get_tools(server_name="company_tools")
        discovered = {tool.name: tool for tool in tools}
        assert "get_incident" in discovered
        result = await discovered["get_incident"].ainvoke({"ticket_id": 482})
        assert "in_progress" in str(result)
        assert upstream.calls == [("get", 482)]
    finally:
        server.should_exit = True
        thread.join(timeout=5)
