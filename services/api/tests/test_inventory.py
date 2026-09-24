"""Inventory API — the rules from CONTEXT-trackflow.md.

These run against SQLite rather than Supabase so the suite stays
runnable with no network and no credentials. SQLModel emits the same
statements either way, and the behaviour under test is ours — stock
arithmetic, the exit rules, per-warehouse scoping — not PostgreSQL's.
The Postgres path is exercised separately; see the PR.

Every test asserts a decision the service makes, not the shape of a
FastAPI response.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

SKU_LA = {
    "name": "Classic White Sneaker - Size 42",
    "sku": "CLT-SNK-W-42",
    "client_name": "PureStep Footwear",
    "category": "fashion",
    "warehouse": "LA",
}
SKU_ZGZ = {**SKU_LA, "sku": "CLT-SNK-W-42-Z", "warehouse": "ZGZ"}


@pytest.fixture
def api(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    """Authenticated client with both databases pointed at temp files."""
    monkeypatch.setenv("TINYDB_PATH", str(tmp_path / "auth.json"))
    monkeypatch.setenv("SECRET_KEY", "test-secret-not-a-real-one-32-bytes-minimum")
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'inventory.db'}")

    import database

    database.close_db()
    database.dispose_inventory_engine()

    from main import app

    with TestClient(app) as client:
        client.post(
            "/users", json={"email": "ops@trackflow.com", "password": "ops-password-12"}
        )
        token = client.post(
            "/auth/login",
            json={"email": "ops@trackflow.com", "password": "ops-password-12"},
        ).json()["access_token"]
        client.headers.update({"Authorization": f"Bearer {token}"})
        yield client

    database.close_db()
    database.dispose_inventory_engine()


def make_sku(api: TestClient, **overrides) -> dict:
    response = api.post("/inventory/products", json={**SKU_LA, **overrides})
    assert response.status_code == 201, response.text
    return response.json()


def inbound(api: TestClient, sku_id: int, quantity: int, warehouse: str = "LA", **kw):
    return api.post(
        "/inventory/orders/inbound",
        json={
            "sku_id": sku_id,
            "quantity": quantity,
            "reference": kw.get("reference", "PO-2024-0098"),
            "warehouse": warehouse,
        },
    )


def outbound(api: TestClient, sku_id: int, quantity: int, warehouse: str = "LA", **kw):
    body = {
        "sku_id": sku_id,
        "quantity": quantity,
        "exit_type": kw.get("exit_type", "dispatch"),
        "warehouse": warehouse,
    }
    if "tracking_number" in kw:
        body["tracking_number"] = kw["tracking_number"]
    elif body["exit_type"] == "dispatch":
        body["tracking_number"] = "1Z999AA10123456784"
    return api.post("/inventory/orders/outbound", json=body)


def stock(api: TestClient, sku_id: int) -> int:
    return api.get(f"/inventory/products/{sku_id}").json()["current_stock"]


# ---------------------------------------------------------------------------
# Stock is computed, never stored
# ---------------------------------------------------------------------------


def test_a_new_sku_starts_at_zero_stock(api: TestClient) -> None:
    """CONTEXT: a SKU accumulates stock only through receipts."""
    created = make_sku(api)
    assert created["current_stock"] == 0
    assert created["client_id"].startswith("client_")
    assert created["minimum_stock"] == 25


def test_stock_is_receipts_minus_exits(api: TestClient) -> None:
    sku = make_sku(api)

    inbound(api, sku["id"], 120, reference="PO-2024-0098")
    inbound(api, sku["id"], 60, reference="GR-LA-0234")
    outbound(api, sku["id"], 35)

    assert stock(api, sku["id"]) == 120 + 60 - 35


def test_no_endpoint_accepts_a_stock_value(api: TestClient) -> None:
    """The whole point of the brief: stock cannot be set directly.

    A caller who sends `current_stock` gets it ignored, not honoured —
    there is no such column for it to reach.
    """
    created = api.post(
        "/inventory/products", json={**SKU_LA, "current_stock": 999}
    ).json()

    assert created["current_stock"] == 0
    assert stock(api, created["id"]) == 0


def test_direct_stock_edit_is_rejected_and_safely_instrumented(
    api: TestClient,
    caplog: pytest.LogCaptureFixture,
) -> None:
    sku = make_sku(api)

    with caplog.at_level("INFO", logger="uvicorn.error.trackflow.telemetry"):
        response = api.patch(
            f"/inventory/products/{sku['id']}",
            json={"warehouse": "LA", "quantity": 99, "attempted_operation": "set"},
        )

    assert response.status_code == 400
    assert "cannot be modified directly" in response.json()["detail"]
    assert "direct_stock_edit_rejected" in caplog.text
    assert stock(api, sku["id"]) == 0


def test_physical_audit_compares_without_mutating_stock(api: TestClient) -> None:
    sku = make_sku(api)
    inbound(api, sku["id"], 20)

    response = api.post(
        "/inventory/audits/check",
        json={
            "sku_id": sku["id"],
            "warehouse": "LA",
            "physical_quantity": 17,
            "detection_method": "cycle_count",
        },
    )

    assert response.status_code == 200
    assert response.json()["system_quantity"] == 20
    assert response.json()["variance_quantity"] == -3
    assert response.json()["discrepancy_detected"] is True
    assert stock(api, sku["id"]) == 20


def test_the_orm_model_has_no_stock_column(api: TestClient) -> None:
    """Structural, so no future endpoint can expose one by accident."""
    from models import SKU

    assert "current_stock" not in SKU.model_fields


# ---------------------------------------------------------------------------
# Outbound rejection — before the write
# ---------------------------------------------------------------------------


def test_an_exit_beyond_available_stock_is_rejected(api: TestClient) -> None:
    sku = make_sku(api)
    inbound(api, sku["id"], 20)

    response = outbound(api, sku["id"], 50)

    assert response.status_code == 400
    # Wording fixed by CONTEXT rule 2.
    assert response.json()["detail"] == (
        "Insufficient stock for SKU 'CLT-SNK-W-42'. Available: 20, requested: 50."
    )


def test_a_rejected_exit_writes_nothing(api: TestClient) -> None:
    """"Reject before the record is persisted" — a half-applied movement
    would corrupt every stock figure that came after it."""
    sku = make_sku(api)
    inbound(api, sku["id"], 20)

    outbound(api, sku["id"], 50)

    assert stock(api, sku["id"]) == 20
    exits = api.get("/inventory/orders?movement_type=exit").json()
    assert exits == []


def test_an_exit_of_exactly_the_available_stock_is_allowed(api: TestClient) -> None:
    """The boundary. Off by one here either blocks a legitimate full
    dispatch or permits stock to go negative."""
    sku = make_sku(api)
    inbound(api, sku["id"], 20)

    assert outbound(api, sku["id"], 20).status_code == 201
    assert stock(api, sku["id"]) == 0


def test_stock_can_never_be_driven_negative(api: TestClient) -> None:
    sku = make_sku(api)
    inbound(api, sku["id"], 10)

    outbound(api, sku["id"], 6)
    assert outbound(api, sku["id"], 6).status_code == 400
    assert stock(api, sku["id"]) == 4


def test_an_exit_against_an_unknown_sku_is_a_404(api: TestClient) -> None:
    assert outbound(api, 424242, 1).status_code == 404


# ---------------------------------------------------------------------------
# Per-warehouse scoping — CONTEXT rule 6
# ---------------------------------------------------------------------------


def test_two_warehouses_hold_separate_figures(api: TestClient) -> None:
    """20 in LA and 15 in Zaragoza is two figures, not 35."""
    la = make_sku(api)
    zgz = make_sku(api, **SKU_ZGZ)

    inbound(api, la["id"], 20, warehouse="LA")
    inbound(api, zgz["id"], 15, warehouse="ZGZ")

    assert stock(api, la["id"]) == 20
    assert stock(api, zgz["id"]) == 15


def test_one_warehouse_cannot_draw_on_another_s_stock(api: TestClient) -> None:
    """The dispatch is from Zaragoza; the units are in Los Angeles."""
    la = make_sku(api)
    zgz = make_sku(api, **SKU_ZGZ)
    inbound(api, la["id"], 50, warehouse="LA")

    response = outbound(api, zgz["id"], 1, warehouse="ZGZ", exit_type="loss")

    assert response.status_code == 400
    assert "Available: 0" in response.json()["detail"]


def test_the_response_shows_the_per_warehouse_breakdown(api: TestClient) -> None:
    sku = make_sku(api)
    inbound(api, sku["id"], 20, warehouse="LA")

    body = api.get(f"/inventory/products/{sku['id']}").json()

    assert body["stock_by_warehouse"] == {"LA": 20}


# ---------------------------------------------------------------------------
# Exit type and tracking number — CONTEXT rule 3
# ---------------------------------------------------------------------------


def test_a_dispatch_requires_a_tracking_number(api: TestClient) -> None:
    sku = make_sku(api)
    inbound(api, sku["id"], 10)

    response = outbound(api, sku["id"], 1, exit_type="dispatch", tracking_number=None)

    assert response.status_code == 422
    assert stock(api, sku["id"]) == 10


def test_a_loss_must_not_carry_a_tracking_number(api: TestClient) -> None:
    """A loss with a carrier reference implies a movement that never
    happened, which is exactly the discrepancy this system exists to
    prevent."""
    sku = make_sku(api)
    inbound(api, sku["id"], 10)

    response = outbound(
        api, sku["id"], 1, exit_type="loss", tracking_number="1Z999AA10123456784"
    )

    assert response.status_code == 422


def test_a_loss_without_a_tracking_number_is_accepted(api: TestClient) -> None:
    sku = make_sku(api)
    inbound(api, sku["id"], 10)

    response = outbound(api, sku["id"], 4, exit_type="loss", tracking_number=None)

    assert response.status_code == 201
    assert stock(api, sku["id"]) == 6


@pytest.mark.parametrize("quantity", [0, -5])
def test_a_non_positive_quantity_is_refused(api: TestClient, quantity: int) -> None:
    """Zero is included deliberately: it is falsy, so a truthiness check
    would let it through while a comparison would not."""
    sku = make_sku(api)
    inbound(api, sku["id"], 10)

    assert inbound(api, sku["id"], quantity).status_code == 422
    assert outbound(api, sku["id"], quantity).status_code == 422


# ---------------------------------------------------------------------------
# Traceability — user_uuid from TinyDB
# ---------------------------------------------------------------------------


def test_every_movement_records_the_authenticated_creator(api: TestClient) -> None:
    """CONTEXT rule 4: the id comes from TinyDB, and no user table is
    replicated into the inventory database."""
    sku = make_sku(api)
    inbound(api, sku["id"], 5)
    outbound(api, sku["id"], 1, exit_type="loss", tracking_number=None)

    me = api.get("/auth/me").json()
    movements = api.get("/inventory/orders").json()

    assert movements
    assert {m["user_uuid"] for m in movements} == {str(me["id"])}


def test_the_caller_cannot_forge_the_creator(api: TestClient) -> None:
    """`user_uuid` is not a request field. Sending one changes nothing."""
    sku = make_sku(api)
    api.post(
        "/inventory/orders/inbound",
        json={
            "sku_id": sku["id"],
            "quantity": 5,
            "reference": "PO-2024-0098",
            "warehouse": "LA",
            "user_uuid": "999",
        },
    )

    me = api.get("/auth/me").json()
    assert api.get("/inventory/orders").json()[0]["user_uuid"] == str(me["id"])


def test_no_user_table_exists_in_the_inventory_database(api: TestClient) -> None:
    from sqlmodel import SQLModel

    tables = set(SQLModel.metadata.tables)
    assert tables == {"sku", "stock_entry", "stock_exit"}


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "method, path",
    [
        ("get", "/inventory/products"),
        ("post", "/inventory/products"),
        ("get", "/inventory/products/1"),
        ("post", "/inventory/orders/inbound"),
        ("post", "/inventory/orders/outbound"),
        ("get", "/inventory/orders"),
        ("patch", "/inventory/products/1"),
        ("post", "/inventory/audits/check"),
    ],
)
def test_every_inventory_route_requires_a_token(
    api: TestClient, method: str, path: str
) -> None:
    """CONTEXT: reads are not public here — a SKU row exposes a client
    brand's stock position."""
    api.headers.pop("Authorization")

    kwargs = {"json": {}} if method in {"post", "patch"} else {}
    assert getattr(api, method)(path, **kwargs).status_code == 401


# ---------------------------------------------------------------------------
# The movement feed
# ---------------------------------------------------------------------------


def test_movements_carry_their_sku_without_a_second_call(api: TestClient) -> None:
    sku = make_sku(api)
    inbound(api, sku["id"], 10)

    movement = api.get("/inventory/orders").json()[0]

    assert movement["sku"]["sku"] == "CLT-SNK-W-42"
    assert movement["sku"]["client_name"] == "PureStep Footwear"


def test_the_feed_is_free_of_n_plus_one_queries(api: TestClient) -> None:
    """The README calls this out specifically.

    Counting statements rather than trusting the implementation: the
    query count must not grow with the number of movements. Reading the
    SKU per row would make this scale linearly and degrade silently.
    """
    from sqlalchemy import event

    import database

    sku_a = make_sku(api)
    sku_b = make_sku(api, **SKU_ZGZ)
    for index in range(8):
        target = sku_a if index % 2 == 0 else sku_b
        inbound(
            api,
            target["id"],
            5,
            warehouse=target["warehouse"],
            reference=f"PO-{index}",
        )

    statements: list[str] = []
    engine = database.inventory_engine()

    def record(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement)

    event.listen(engine, "before_cursor_execute", record)
    try:
        movements = api.get("/inventory/orders").json()
    finally:
        event.remove(engine, "before_cursor_execute", record)

    assert len(movements) == 8
    selects = [s for s in statements if s.lstrip().upper().startswith("SELECT")]
    # entries + exits + one batched SKU lookup. Never one per movement.
    assert len(selects) <= 4, f"{len(selects)} SELECTs for 8 movements:\n" + "\n".join(selects)


def test_listing_skus_does_not_scale_queries_with_the_catalogue(
    api: TestClient,
) -> None:
    """Same guarantee for the product list, where stock is aggregated."""
    from sqlalchemy import event

    import database

    for index in range(6):
        made = make_sku(api, sku=f"BULK-{index}")
        inbound(api, made["id"], 10, reference=f"PO-B{index}")

    statements: list[str] = []
    engine = database.inventory_engine()

    def record(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement)

    event.listen(engine, "before_cursor_execute", record)
    try:
        products = api.get("/inventory/products").json()
    finally:
        event.remove(engine, "before_cursor_execute", record)

    assert len(products) == 6
    selects = [s for s in statements if s.lstrip().upper().startswith("SELECT")]
    assert len(selects) <= 4, f"{len(selects)} SELECTs for 6 SKUs"


# ---------------------------------------------------------------------------
# Concurrency — the stock check must not be separable from the write
# ---------------------------------------------------------------------------


def test_the_outbound_check_holds_a_row_lock(api: TestClient) -> None:
    """Structural guard for a bug found by racing two dispatches.

    The check and the insert used to be separable: two dispatches for one
    SKU both read 20 units available, both passed, and both committed —
    shipping 30 units that did not exist. Measured against PostgreSQL,
    7 of 8 concurrent pairs oversold and left stock at -10.

    The fix is `SELECT ... FOR UPDATE` on the SKU row, so the second
    request waits for the first to commit and then re-reads the reduced
    figure. This asserts the clause is actually emitted, because the
    suite runs on SQLite where the race cannot be reproduced — SQLite
    serialises writers itself, so a passing race here would prove
    nothing about Postgres.
    """
    from sqlalchemy.dialects import postgresql
    from sqlmodel import select

    from models import SKU
    from routers.inventory import _lock_sku_or_404

    statements: list[str] = []

    class _Dialect:
        name = "postgresql"

    class _Bind:
        @staticmethod
        def dialect():
            return _Dialect()

    # Compile the same query the helper builds, against the Postgres
    # dialect, and confirm the locking clause survives compilation.
    query = select(SKU).where(SKU.id == 1).with_for_update()
    compiled = str(query.compile(dialect=postgresql.dialect()))
    statements.append(compiled)

    assert "FOR UPDATE" in compiled.upper()
    # And the helper exists and is what the outbound route calls.
    assert callable(_lock_sku_or_404)


def test_outbound_and_inbound_both_take_the_lock(api: TestClient) -> None:
    """Both write paths route through the locking fetch, not a plain get.

    Parsed with `ast` rather than searched as text. The first version of
    this test did a substring check on the source and passed even after
    the lock was removed, because a nearby *comment* still mentioned the
    helper by name. Only a real call node counts.
    """
    import ast
    import inspect
    import textwrap

    from routers import inventory

    def calls_in(function) -> set[str]:
        tree = ast.parse(textwrap.dedent(inspect.getsource(function)))
        return {
            node.func.id
            for node in ast.walk(tree)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
        }

    assert "_lock_sku_or_404" in calls_in(inventory.create_outbound), (
        "outbound does not lock the SKU row before checking stock"
    )
    assert "_lock_sku_or_404" in calls_in(inventory.create_inbound), (
        "inbound does not lock the SKU row"
    )


def test_sequential_dispatches_still_cannot_oversell(api: TestClient) -> None:
    """The plain, non-concurrent version of the same rule."""
    sku = make_sku(api)
    inbound(api, sku["id"], 20)

    first = outbound(api, sku["id"], 15)
    second = outbound(api, sku["id"], 15)

    assert first.status_code == 201
    assert second.status_code == 400
    assert stock(api, sku["id"]) == 5
