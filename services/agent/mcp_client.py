"""LangChain MCP adapter boundary for TrackFlow's company-tools server."""

from __future__ import annotations

import asyncio
import json
import os
from typing import Any

from langchain_mcp_adapters.client import MultiServerMCPClient


class CompanyToolsMCPClient:
    """Discover and invoke company tools through MCP, never direct repositories."""

    def __init__(self, url: str, access_token: str, timeout_seconds: float = 5.0):
        self.url = url
        self.access_token = access_token
        self.timeout_seconds = timeout_seconds

    @classmethod
    def from_env(cls) -> CompanyToolsMCPClient:
        return cls(
            url=os.getenv("COMPANY_MCP_URL", "http://company-tools-mcp:8010/mcp").strip(),
            access_token=os.getenv("COMPANY_MCP_ACCESS_TOKEN", "").strip(),
            timeout_seconds=float(os.getenv("COMPANY_MCP_TIMEOUT_SECONDS", "5.0")),
        )

    async def _invoke(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        if not self.access_token:
            raise RuntimeError("Company-tools MCP access token is not configured")
        client = MultiServerMCPClient(
            {
                "company_tools": {
                    "transport": "streamable_http",
                    "url": self.url,
                    "headers": {
                        "Authorization": f"Bearer {self.access_token}",
                    },
                    "timeout": self.timeout_seconds,
                }
            }
        )
        tools = await client.get_tools(server_name="company_tools")
        selected = next((tool for tool in tools if tool.name == tool_name), None)
        if selected is None:
            raise RuntimeError(f"MCP tool '{tool_name}' was not discovered")
        result = await selected.ainvoke(arguments)
        if isinstance(result, dict):
            return result
        if isinstance(result, str):
            parsed = json.loads(result)
            if isinstance(parsed, dict):
                return parsed
        raise RuntimeError(f"MCP tool '{tool_name}' returned an unsupported result")

    def get_incident(self, ticket_id: int) -> dict[str, Any]:
        return asyncio.run(self._invoke("get_incident", {"ticket_id": ticket_id}))

    def query_inventory(self, query: str) -> list[dict[str, Any]]:
        result = asyncio.run(self._invoke("query_inventory", {"query": query}))
        products = result.get("products")
        if not isinstance(products, list):
            raise RuntimeError("MCP inventory result did not contain a product list")
        return products
