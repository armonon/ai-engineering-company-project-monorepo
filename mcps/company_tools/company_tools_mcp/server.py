"""OAuth-protected Streamable HTTP MCP server for TrackFlow company tools."""

from __future__ import annotations

import contextlib
from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal, TypeVar

from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.exceptions import ToolError
from mcp.types import ToolAnnotations
from mcpauth import MCPAuth
from mcpauth.config import AuthServerConfig, AuthServerType
from mcpauth.types import (
    ResourceServerConfig,
    ResourceServerMetadata,
    VerifyAccessTokenFunction,
)
from mcpauth.utils import fetch_server_config
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.routing import Mount

from .audit import AuditLogger
from .config import Settings
from .schemas import (
    IncidentRecord,
    InventoryProduct,
    InventoryQueryResult,
    RejectedInventoryWrite,
)
from .upstream import CompanyAPI

INCIDENT_READ = "incidents:read"
INCIDENT_WRITE = "incidents:write"
INVENTORY_READ = "inventory:read"
ALL_SCOPES = [INCIDENT_READ, INCIDENT_WRITE, INVENTORY_READ]

T = TypeVar("T")


@dataclass(frozen=True)
class ServerBundle:
    app: Starlette
    mcp: FastMCP
    auth: MCPAuth


def create_server(
    settings: Settings,
    *,
    company_api: CompanyAPI | None = None,
    auth_server: AuthServerConfig | None = None,
    verify_access_token: VerifyAccessTokenFunction | None = None,
) -> ServerBundle:
    """Build the server; dependency injection keeps acceptance tests credential-free."""
    upstream = company_api or CompanyAPI(
        settings.company_api_url,
        settings.company_api_token,
        settings.request_timeout_seconds,
    )
    audit = AuditLogger(settings.audit_log_path)
    authorization_server = auth_server or fetch_server_config(
        settings.issuer_url, AuthServerType.OIDC
    )
    mcp_auth = MCPAuth(
        protected_resources=[
            ResourceServerConfig(
                metadata=ResourceServerMetadata(
                    resource=settings.resource_url,
                    resource_name="TrackFlow company tools",
                    resource_documentation=f"{settings.resource_url}/docs",
                    authorization_servers=[authorization_server],
                    scopes_supported=ALL_SCOPES,
                    bearer_methods_supported=["header"],
                )
            )
        ]
    )
    mcp = FastMCP(
        name="TrackFlow Company Tools",
        instructions=(
            "Use incident tools for live ticket data and lifecycle operations. "
            "Inventory is query-only; every modification attempt is rejected."
        ),
        stateless_http=True,
        json_response=True,
    )

    def run_tool(
        tool: str,
        required_scope: str,
        target_id: int | str | None,
        action: Callable[[], T],
    ) -> T:
        info = mcp_auth.auth_info
        if info is None:
            raise ToolError("AUTH_REQUIRED: a valid OAuth access token is required")
        client_id = info.client_id or "unknown-client"
        if required_scope not in info.scopes:
            audit.record(
                client_id=client_id,
                subject=info.subject,
                tool=tool,
                result="AUTH_SCOPE_MISSING",
                target_id=target_id,
            )
            raise ToolError(f"AUTH_SCOPE_MISSING: tool requires scope '{required_scope}'")
        try:
            result = action()
        except ToolError as exc:
            error_code = str(exc).split(":", 1)[0]
            audit.record(
                client_id=client_id,
                subject=info.subject,
                tool=tool,
                result=error_code,
                target_id=target_id,
            )
            raise
        audit.record(
            client_id=client_id,
            subject=info.subject,
            tool=tool,
            result="success",
            target_id=target_id,
        )
        return result

    @mcp.tool(
        name="get_incident",
        title="Get incident status",
        description=(
            "Read one live TrackFlow incident by integer ticket ID. Returns its "
            "status, category, origin, branch, and timestamps. Requires incidents:read."
        ),
        annotations=ToolAnnotations(
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
        structured_output=True,
    )
    def get_incident(ticket_id: int) -> IncidentRecord:
        return run_tool(
            "get_incident",
            INCIDENT_READ,
            ticket_id,
            lambda: IncidentRecord.model_validate(upstream.get_incident(ticket_id)),
        )

    @mcp.tool(
        name="create_incident",
        title="Create incident",
        description=(
            "Create a TrackFlow incident in the real Incidents Manager. New incidents "
            "start open. Requires incidents:write."
        ),
        annotations=ToolAnnotations(
            readOnlyHint=False,
            destructiveHint=False,
            idempotentHint=False,
            openWorldHint=False,
        ),
        structured_output=True,
    )
    def create_incident(
        title: str,
        description: str,
        category: Literal[
            "lost_parcel",
            "delivery_failure",
            "inventory_discrepancy",
            "carrier_issue",
            "returns_issue",
            "warehouse_incident",
            "system_failure",
            "client_complaint",
            "other",
        ],
        origin: Literal["customer", "branch", "internal"],
        branch: Literal[
            "central",
            "la_warehouse",
            "la_office",
            "zaragoza_warehouse",
            "zaragoza_office",
        ],
    ) -> IncidentRecord:
        payload = {
            "title": title,
            "description": description,
            "category": category,
            "origin": origin,
            "branch": branch,
        }
        return run_tool(
            "create_incident",
            INCIDENT_WRITE,
            None,
            lambda: IncidentRecord.model_validate(upstream.create_incident(payload)),
        )

    @mcp.tool(
        name="update_incident_status",
        title="Advance incident lifecycle",
        description=(
            "Advance one incident through the TrackFlow lifecycle using the dedicated "
            "status endpoint. Requires incidents:write."
        ),
        annotations=ToolAnnotations(
            readOnlyHint=False,
            destructiveHint=False,
            idempotentHint=False,
            openWorldHint=False,
        ),
        structured_output=True,
    )
    def update_incident_status(
        ticket_id: int,
        status: Literal["open", "in_progress", "resolved", "discarded"],
    ) -> IncidentRecord:
        return run_tool(
            "update_incident_status",
            INCIDENT_WRITE,
            ticket_id,
            lambda: IncidentRecord.model_validate(
                upstream.update_incident_status(ticket_id, status)
            ),
        )

    @mcp.tool(
        name="query_inventory",
        title="Query live inventory",
        description=(
            "Read current computed stock from TrackFlow inventory by product name or SKU. "
            "Optionally restrict to LA or ZGZ. Never changes inventory. Requires inventory:read."
        ),
        annotations=ToolAnnotations(
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
        structured_output=True,
    )
    def query_inventory(
        query: str,
        warehouse: Literal["LA", "ZGZ"] | None = None,
    ) -> InventoryQueryResult:
        def action() -> InventoryQueryResult:
            products = upstream.list_inventory(warehouse)
            terms = [term for term in query.lower().split() if len(term) >= 2]
            matches = [
                product
                for product in products
                if not terms
                or any(
                    term in f"{product.get('name', '')} {product.get('sku', '')}".lower()
                    for term in terms
                )
            ]
            return InventoryQueryResult(
                products=[InventoryProduct.model_validate(item) for item in matches],
                count=len(matches),
                read_only=True,
            )

        return run_tool("query_inventory", INVENTORY_READ, query, action)

    @mcp.tool(
        name="attempt_inventory_write",
        title="Inventory write protection check",
        description=(
            "Explicitly demonstrates the inventory permission boundary. Every requested "
            "create, update, or delete operation is rejected with INVENTORY_READ_ONLY."
        ),
        annotations=ToolAnnotations(
            readOnlyHint=False,
            destructiveHint=True,
            idempotentHint=True,
            openWorldHint=False,
        ),
        structured_output=True,
    )
    def attempt_inventory_write(
        operation: Literal["create", "update", "delete"],
        target: str,
    ) -> RejectedInventoryWrite:
        def reject() -> RejectedInventoryWrite:
            raise ToolError(
                "INVENTORY_READ_ONLY: inventory modifications are not permitted through MCP"
            )

        return run_tool("attempt_inventory_write", INVENTORY_READ, target, reject)

    @contextlib.asynccontextmanager
    async def lifespan(_app: Starlette):
        async with mcp.session_manager.run():
            yield

    verifier: Literal["jwt"] | VerifyAccessTokenFunction = (
        verify_access_token if verify_access_token is not None else "jwt"
    )
    bearer_auth = Middleware(
        mcp_auth.bearer_auth_middleware(
            verifier,
            audience=settings.resource_url,
            resource=settings.resource_url,
            show_error_details=False,
        )
    )
    app = Starlette(
        routes=[
            *mcp_auth.resource_metadata_router().routes,
            Mount("/", app=mcp.streamable_http_app(), middleware=[bearer_auth]),
        ],
        lifespan=lifespan,
    )
    return ServerBundle(app=app, mcp=mcp, auth=mcp_auth)
