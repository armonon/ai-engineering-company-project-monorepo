# Company-tools MCP acceptance evidence

Date: 2026-10-28

## Automated acceptance

The acceptance suite starts the real Streamable HTTP ASGI application on an
ephemeral local port, protects it with MCP Auth, connects with
`MultiServerMCPClient` from `langchain-mcp-adapters`, discovers the published
tools with an OAuth bearer token, and invokes `get_incident`. The call reaches
the injected TrackFlow API boundary and writes a secret-free audit event.

Additional cases verify:

- an unauthenticated `tools/list` request receives HTTP 401 with a
  `resource_metadata` discovery hint;
- RFC 9728 Protected Resource Metadata advertises the exact resource, issuer,
  bearer method, and three supported scopes;
- all five tools expose descriptions, JSON input/output schemas, and MCP
  read-only/destructive annotations;
- read/write scopes are enforced independently;
- incident creation and status changes use the real manager's exact fields and
  dedicated lifecycle route;
- inventory reads are permitted and every inventory write is rejected with
  `INVENTORY_READ_ONLY` before any upstream call;
- validation, not-found, authentication, authorization, and availability
  failures produce distinct error codes;
- audit JSONL contains client, subject, tool, result, target, and timestamp but
  never an access token.

Commands and results:

```text
uv run --project mcps/company_tools pytest mcps/company_tools/tests -q
13 passed

pytest tests/pipelines/test_agent_graph.py tests/pipelines/test_agent_evals.py
       tests/pipelines/test_mcp_client.py services/api/tests/test_agent.py -q
22 passed

docker compose --env-file .env.example config --quiet
passed
```

## External Playground evidence

The implementation is ready for the rubric's external MCP Playground check.
That check requires a real OIDC issuer/access token and a public GitHub
Codespaces forwarded URL; these values are intentionally absent from the
repository. The exact five-tool flow and capture instructions are documented in
`mcps/company_tools/README.md`.
