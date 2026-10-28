from __future__ import annotations

from typing import ClassVar

import pytest
from trackflow_agent import CompanyToolsMCPClient


class FakeTool:
    def __init__(self, name: str, result):
        self.name = name
        self.result = result
        self.calls = []

    async def ainvoke(self, arguments):
        self.calls.append(arguments)
        return self.result


class FakeMultiServerClient:
    connections = None
    requested_server = None
    tools: ClassVar[list] = []

    def __init__(self, connections):
        type(self).connections = connections

    async def get_tools(self, *, server_name=None):
        type(self).requested_server = server_name
        return type(self).tools


def test_incident_lookup_is_discovered_and_invoked_through_adapter(monkeypatch):
    tool = FakeTool("get_incident", '{"id": 482, "status": "in_progress"}')
    FakeMultiServerClient.tools = [tool]
    monkeypatch.setattr("trackflow_agent.mcp_client.MultiServerMCPClient", FakeMultiServerClient)
    client = CompanyToolsMCPClient("https://mcp.example.test/mcp", "oauth-access-token", 4.0)

    result = client.get_incident(482)

    assert result == {"id": 482, "status": "in_progress"}
    assert tool.calls == [{"ticket_id": 482}]
    assert FakeMultiServerClient.requested_server == "company_tools"
    connection = FakeMultiServerClient.connections["company_tools"]
    assert connection["transport"] == "streamable_http"
    assert connection["headers"]["Authorization"] == "Bearer oauth-access-token"


def test_inventory_lookup_returns_products_from_mcp(monkeypatch):
    tool = FakeTool(
        "query_inventory",
        {"products": [{"id": 4, "sku": "TEC-CHG-065", "current_stock": 31}]},
    )
    FakeMultiServerClient.tools = [tool]
    monkeypatch.setattr("trackflow_agent.mcp_client.MultiServerMCPClient", FakeMultiServerClient)
    client = CompanyToolsMCPClient("https://mcp.example.test/mcp", "token")

    products = client.query_inventory("TEC-CHG-065 stock")

    assert products[0]["current_stock"] == 31
    assert tool.calls == [{"query": "TEC-CHG-065 stock"}]


def test_missing_access_token_fails_before_discovery():
    client = CompanyToolsMCPClient("https://mcp.example.test/mcp", "")
    with pytest.raises(RuntimeError, match="access token is not configured"):
        client.get_incident(482)
