# TrackFlow company-tools MCP server

This independent MCP resource server exposes TrackFlow's existing incident and
inventory APIs through Streamable HTTP. Streamable HTTP was chosen instead of
stdio because the server is intended for multiple local and remote clients;
unlike a child process, it has a network boundary that can be protected with
OAuth and audited centrally.

## Security model

MCP Auth (`mcpauth`) runs in OAuth 2.1/OIDC resource-server mode. It publishes
RFC 9728 Protected Resource Metadata at
`/.well-known/oauth-protected-resource/mcp`, validates bearer JWTs from the
configured issuer, checks the token audience against `MCP_RESOURCE_URL`, and
rejects unauthenticated MCP discovery and invocation.

Scopes are deliberately narrow:

| Scope | Allowed tools |
| --- | --- |
| `incidents:read` | `get_incident` |
| `incidents:write` | `create_incident`, `update_incident_status` |
| `inventory:read` | `query_inventory`; the write-protection check |

Inventory has no writable MCP capability. `attempt_inventory_write` exists so
clients can verify the boundary: every create/update/delete request returns
`INVENTORY_READ_ONLY` and never calls the upstream API.

Each invocation appends client ID, subject, tool, result code, target, and UTC
timestamp to `MCP_AUDIT_LOG`. Access tokens and request payloads are never
logged.

## Discoverable tools

| Tool | Contract |
| --- | --- |
| `get_incident(ticket_id)` | Live status/category/origin/branch/timestamps |
| `create_incident(...)` | Exact TrackFlow fields and closed value sets |
| `update_incident_status(ticket_id, status)` | Uses `PATCH /api/incidents/{id}/status` |
| `query_inventory(query, warehouse?)` | Computed stock from `GET /inventory/products` |
| `attempt_inventory_write(operation, target)` | Controlled read-only rejection |

FastMCP publishes the descriptions, JSON input schemas, structured result
schemas, and read-only/destructive annotations through standard `tools/list`.

## Configuration and start

Copy the root `.env.example` to `.env`, configure a compliant OIDC issuer with
the three scopes above, and provide two separate tokens:

- `COMPANY_API_TOKEN`: backend-to-backend token used by the MCP server;
- `COMPANY_MCP_ACCESS_TOKEN`: OAuth token used by the LangGraph MCP client.

Then enable the secure MCP profile alongside the core platform:

```bash
docker compose --profile mcp up --build
```

The MCP endpoint is `http://localhost:8010/mcp`. No secret is present in the
Compose file, Dockerfile, or repository.

## Error contract

| Boundary | Code/status | Meaning |
| --- | --- | --- |
| MCP HTTP | `401` + `WWW-Authenticate` | missing/invalid bearer token |
| MCP HTTP | `403` | globally required OAuth scope missing |
| Tool | `AUTH_SCOPE_MISSING` | valid client lacks this tool's scope |
| Tool | `VALIDATION_ERROR` | TrackFlow field/lifecycle validation failed |
| Tool | `UPSTREAM_NOT_FOUND` | incident or inventory record absent |
| Tool | `UPSTREAM_AUTH_FAILED` / `UPSTREAM_FORBIDDEN` | service token rejected |
| Tool | `UPSTREAM_UNAVAILABLE` | timeout, network failure, or upstream 5xx |
| Tool | `INVENTORY_READ_ONLY` | any inventory write attempt |

## Validation

Automated acceptance coverage verifies unauthenticated `401`, public Protected
Resource Metadata, complete tool discovery, scopes, incident create/read/status
flows, inventory query/rejection, and one secret-free audit record per call:

```bash
uv run --project mcps/company_tools \
  pytest mcps/company_tools/tests -q \
  -o asyncio_default_fixture_loop_scope=function
```

For the external review, expose port 8010 from GitHub Codespaces as **public**,
set `MCP_RESOURCE_URL` to that forwarded `/mcp` URL, and connect MCP Playground
with an access token from `MCP_AUTH_ISSUER`. Run all five discovered tools and
capture the controlled `INVENTORY_READ_ONLY` result. `localhost` cannot be used
by the hosted Playground.

## Agent migration

`services/agent/mcp_client.py` uses `langchain-mcp-adapters` to discover tools
over Streamable HTTP and invoke them with OAuth. The previous API router's
direct TinyDB/SQLModel readers were removed; the compiled graph retains its
existing RAG/tool routing and timeout fallbacks while every operational lookup
now crosses this MCP boundary.
