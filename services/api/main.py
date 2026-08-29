"""TrackFlow backend API.

One FastAPI service, routes grouped by domain — the modular-monolith
shape proposed in docs/ARCHITECTURE_PROPOSAL.md.

    routes/suppliers.py   supplier directory (TinyDB)
    routes/incidents.py   incident-report analysis (CSV upload)

Run it:
    uv run uvicorn main:app --reload        # from services/api/
"""

from __future__ import annotations

import logging
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from routers.auth import router as auth_router
from routers.incidents import router as incidents_router
from routers.incidents_manager import router as incidents_manager_router
from routers.inventory import router as inventory_router
from routers.profiles import router as profiles_router
from routers.suppliers import router as suppliers_router
from routers.users import router as users_router

logger = logging.getLogger("trackflow.api")


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Startup: make sure the inventory tables exist in Supabase.

    Deliberately non-fatal when DATABASE_URL is absent. The inventory
    routes will fail loudly on use, but auth, suppliers and incidents —
    which live in TinyDB and have nothing to do with Supabase — keep
    serving. One unconfigured subsystem should not stop the API booting,
    and the test suite runs without Postgres because of it.

    Uses the lifespan contextmanager rather than @app.on_event, which
    FastAPI has deprecated.
    """
    from database import create_inventory_schema

    try:
        if create_inventory_schema():
            logger.info("Inventory schema ready in Supabase")
        else:
            logger.warning(
                "DATABASE_URL not set - /inventory routes are unavailable. "
                "See services/api/.env.example."
            )
    except Exception:
        logger.exception("Could not initialise the inventory schema")

    yield


app = FastAPI(
    lifespan=lifespan,
    title="TrackFlow API",
    description=(
        "Supplier directory (TinyDB) and incident-report analysis for "
        "TrackFlow's Los Angeles and Zaragoza operations."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# Explicit origins for the two uis/* dev servers — never "*".
# See docs/ARCHITECTURE_PROPOSAL.md § 6.2.
DEFAULT_ALLOWED_ORIGINS = (
    "http://localhost:3000",
    "http://localhost:3001",
    "http://localhost:3100",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:3001",
    "http://127.0.0.1:3100",
)


def allowed_origins() -> list[str]:
    configured = os.environ.get("ALLOWED_ORIGINS", "")
    origins = [origin.strip().rstrip("/") for origin in configured.split(",") if origin.strip()]
    if not origins:
        return list(DEFAULT_ALLOWED_ORIGINS)
    if "*" in origins:
        raise RuntimeError("ALLOWED_ORIGINS must list explicit browser origins, never '*'.")
    return origins

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Last line of defence for anything no route caught.

    Two things were wrong without this. Starlette's default body for an
    unhandled exception is the plain text `Internal Server Error`, but
    every frontend caller parses responses as JSON — so a backend bug
    surfaced to the user as
    `SyntaxError: Unexpected token 'I' ... is not valid JSON`, which
    tells them nothing and looks like a frontend crash.

    And the detail of the failure belongs in the server log, not in the
    response: exception text routinely carries filesystem paths, query
    fragments, and library internals.

    So: the real exception is logged with its traceback here, and the
    client gets a fixed, structured, human-readable body.
    """
    logger.exception(
        "Unhandled exception on %s %s", request.method, request.url.path, exc_info=exc
    )
    return JSONResponse(
        status_code=500,
        content={
            "detail": (
                "Something went wrong on our end. The team has been notified — "
                "please try again, and contact support if it keeps happening."
            )
        },
    )


app.include_router(auth_router)
app.include_router(users_router)
app.include_router(profiles_router)
app.include_router(suppliers_router)
app.include_router(incidents_manager_router)
app.include_router(incidents_router)
app.include_router(inventory_router)


@app.get("/", tags=["health"])
def health() -> dict[str, str]:
    return {"status": "ok", "service": "trackflow-api"}
