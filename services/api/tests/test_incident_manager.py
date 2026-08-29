"""Incident manager tests — model, lifecycle, endpoints, seed totals.

Every expected number comes from CONTEXT.md.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

VALID = {
    "title": "Parcel missing from the Zaragoza outbound bay",
    "description": "Scanned in at 09:14 but not present at the loading dock.",
    "category": "lost_parcel",
    "origin": "branch",
    "branch": "zaragoza_warehouse",
}


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    """Authenticated client on a throwaway TinyDB."""
    monkeypatch.setenv("TINYDB_PATH", str(tmp_path / "incidents.json"))
    monkeypatch.setenv("SECRET_KEY", "test-secret-not-a-real-one-32-bytes-minimum")
    monkeypatch.setenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60")

    import database

    database.close_db()

    from main import app

    with TestClient(app) as c:
        c.post(
            "/users",
            json={"email": "ops@trackflow.com", "password": "test-password-123"},
        )
        token = c.post(
            "/auth/login",
            json={"email": "ops@trackflow.com", "password": "test-password-123"},
        ).json()["access_token"]
        c.headers.update({"Authorization": f"Bearer {token}"})
        yield c

    database.close_db()


def create(client: TestClient, **overrides) -> dict:
    r = client.post("/api/incidents", json={**VALID, **overrides})
    assert r.status_code == 201, r.text
    return r.json()


# ---------------------------------------------------------------------------
# Model + creation
# ---------------------------------------------------------------------------


def test_create_returns_the_full_record(client: TestClient) -> None:
    body = create(client)
    assert body["id"] >= 1
    assert body["title"] == VALID["title"]
    assert body["category"] == "lost_parcel"
    assert body["origin"] == "branch"
    assert body["branch"] == "zaragoza_warehouse"
    # New incidents start at the beginning of the lifecycle.
    assert body["status"] == "open"
    # Timestamps are generated, not supplied.
    assert body["created_at"] and body["updated_at"]


def test_seed_bookkeeping_field_is_never_exposed(client: TestClient) -> None:
    """`source_incident_id` is duplicate control, not part of the model."""
    body = create(client)
    assert "source_incident_id" not in body


@pytest.mark.parametrize("field", ["title", "description", "category", "origin", "branch"])
def test_missing_required_field_is_400_naming_the_field(
    client: TestClient, field: str
) -> None:
    payload = {k: v for k, v in VALID.items() if k != field}
    r = client.post("/api/incidents", json=payload)
    assert r.status_code == 400
    assert r.json()["detail"]["field"] == field
    assert r.json()["detail"]["message"]


@pytest.mark.parametrize(
    ("field", "bad"),
    [
        ("category", "not_a_category"),
        ("origin", "somewhere"),
        ("branch", "mars_office"),
        ("status", "archived"),
    ],
)
def test_invalid_enum_value_is_400_naming_the_field(
    client: TestClient, field: str, bad: str
) -> None:
    r = client.post("/api/incidents", json={**VALID, field: bad})
    assert r.status_code == 400
    detail = r.json()["detail"]
    assert detail["field"] == field
    # The message lists what IS allowed, so the caller can recover.
    assert "Allowed:" in detail["message"]


def test_blank_title_is_rejected(client: TestClient) -> None:
    r = client.post("/api/incidents", json={**VALID, "title": "   "})
    assert r.status_code == 400
    assert r.json()["detail"]["field"] == "title"


def test_all_nine_categories_are_accepted(client: TestClient) -> None:
    categories = [
        "lost_parcel", "delivery_failure", "inventory_discrepancy",
        "carrier_issue", "returns_issue", "warehouse_incident",
        "system_failure", "client_complaint", "other",
    ]
    for category in categories:
        r = client.post("/api/incidents", json={**VALID, "category": category})
        assert r.status_code == 201, f"{category} rejected"


def test_all_five_branches_are_accepted(client: TestClient) -> None:
    for branch in [
        "central", "la_warehouse", "la_office",
        "zaragoza_warehouse", "zaragoza_office",
    ]:
        r = client.post("/api/incidents", json={**VALID, "branch": branch})
        assert r.status_code == 201, f"{branch} rejected"


# ---------------------------------------------------------------------------
# Lifecycle
# ---------------------------------------------------------------------------


def patch_status(client: TestClient, incident_id: int, status: str):
    return client.patch(f"/api/incidents/{incident_id}/status", json={"status": status})


@pytest.mark.parametrize(
    ("start", "target"),
    [("open", "in_progress"), ("open", "discarded")],
)
def test_valid_transitions_from_open(client: TestClient, start: str, target: str) -> None:
    incident = create(client)
    r = patch_status(client, incident["id"], target)
    assert r.status_code == 200
    assert r.json()["status"] == target


@pytest.mark.parametrize("target", ["resolved", "discarded"])
def test_valid_transitions_from_in_progress(client: TestClient, target: str) -> None:
    incident = create(client)
    patch_status(client, incident["id"], "in_progress")
    r = patch_status(client, incident["id"], target)
    assert r.status_code == 200
    assert r.json()["status"] == target


def test_open_cannot_jump_straight_to_resolved(client: TestClient) -> None:
    """CONTEXT allows open -> in_progress -> resolved, not open -> resolved."""
    incident = create(client)
    r = patch_status(client, incident["id"], "resolved")
    assert r.status_code == 400
    assert "in_progress" in r.json()["detail"]["message"]


@pytest.mark.parametrize("final", ["resolved", "discarded"])
def test_final_states_cannot_change(client: TestClient, final: str) -> None:
    incident = create(client)
    patch_status(client, incident["id"], "in_progress")
    patch_status(client, incident["id"], final)

    r = patch_status(client, incident["id"], "open")
    assert r.status_code == 400
    assert "final state" in r.json()["detail"]["message"]


def test_transition_to_the_same_status_is_rejected(client: TestClient) -> None:
    incident = create(client)
    r = patch_status(client, incident["id"], "open")
    assert r.status_code == 400
    assert "already" in r.json()["detail"]["message"]


def test_invalid_status_value_on_patch_is_400(client: TestClient) -> None:
    incident = create(client)
    r = patch_status(client, incident["id"], "archived")
    assert r.status_code == 400
    assert r.json()["detail"]["field"] == "status"


def test_patch_status_on_missing_incident_is_404(client: TestClient) -> None:
    r = patch_status(client, 9999, "in_progress")
    assert r.status_code == 404


def test_status_change_updates_the_timestamp(client: TestClient) -> None:
    incident = create(client)
    before = incident["updated_at"]
    after = patch_status(client, incident["id"], "in_progress").json()["updated_at"]
    assert after >= before


# ---------------------------------------------------------------------------
# Listing and filters
# ---------------------------------------------------------------------------


def test_list_is_empty_on_a_fresh_database(client: TestClient) -> None:
    """Read endpoints must not fail on an empty database."""
    r = client.get("/api/incidents")
    assert r.status_code == 200
    assert r.json() == []


def test_list_returns_everything_with_no_filters(client: TestClient) -> None:
    create(client)
    create(client, category="system_failure")
    assert len(client.get("/api/incidents").json()) == 2


@pytest.mark.parametrize(
    ("param", "value"),
    [
        ("origin", "branch"),
        ("branch", "zaragoza_warehouse"),
        ("category", "lost_parcel"),
    ],
)
def test_each_filter_works(client: TestClient, param: str, value: str) -> None:
    create(client)
    create(client, origin="internal", branch="central", category="system_failure")

    r = client.get("/api/incidents", params={param: value})
    assert r.status_code == 200
    assert all(item[param] == value for item in r.json())
    assert len(r.json()) == 1


def test_status_filter_works(client: TestClient) -> None:
    """Both incidents start 'open', so one is advanced to make the
    filter discriminate."""
    stays_open = create(client)
    advanced = create(client)
    patch_status(client, advanced["id"], "in_progress")

    open_only = client.get("/api/incidents", params={"status": "open"}).json()
    assert [i["id"] for i in open_only] == [stays_open["id"]]

    in_progress = client.get(
        "/api/incidents", params={"status": "in_progress"}
    ).json()
    assert [i["id"] for i in in_progress] == [advanced["id"]]


def test_filters_combine(client: TestClient) -> None:
    create(client)
    create(client, category="carrier_issue")
    r = client.get(
        "/api/incidents",
        params={"origin": "branch", "category": "carrier_issue"},
    )
    assert len(r.json()) == 1


def test_unknown_filter_value_is_422(client: TestClient) -> None:
    assert client.get("/api/incidents", params={"status": "nope"}).status_code == 422
    assert client.get("/api/incidents", params={"branch": "nope"}).status_code == 422


def test_get_one_incident(client: TestClient) -> None:
    incident = create(client)
    r = client.get(f"/api/incidents/{incident['id']}")
    assert r.status_code == 200
    assert r.json()["id"] == incident["id"]


def test_get_missing_incident_is_404(client: TestClient) -> None:
    r = client.get("/api/incidents/9999")
    assert r.status_code == 404
    assert "9999" in r.json()["detail"]


def test_summary_route_is_not_shadowed_by_the_id_route(client: TestClient) -> None:
    """/summary is a literal segment and must win over /{incident_id}."""
    r = client.get("/api/incidents/summary")
    assert r.status_code == 200
    assert "by_status" in r.json()


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------


def test_summary_on_an_empty_database_returns_zeros(client: TestClient) -> None:
    r = client.get("/api/incidents/summary")
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 0
    # Every key is present at zero, so the UI can render stable tiles.
    assert set(body["by_status"]) == {"open", "in_progress", "resolved", "discarded"}
    assert all(v == 0 for v in body["by_status"].values())
    assert len(body["by_category"]) == 9
    assert len(body["by_branch"]) == 5


def test_summary_counts_by_every_dimension(client: TestClient) -> None:
    create(client)                                        # branch / lost_parcel
    create(client, origin="internal", branch="central", category="system_failure")
    incident = create(client, origin="customer", branch="la_office")
    patch_status(client, incident["id"], "in_progress")

    body = client.get("/api/incidents/summary").json()
    assert body["total"] == 3
    assert body["by_status"]["open"] == 2
    assert body["by_status"]["in_progress"] == 1
    assert body["by_origin"] == {"customer": 1, "branch": 1, "internal": 1}
    assert body["by_branch"]["central"] == 1
    assert body["by_category"]["system_failure"] == 1


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("post", "/api/incidents"),
        ("get", "/api/incidents"),
        ("get", "/api/incidents/summary"),
        ("get", "/api/incidents/1"),
        ("patch", "/api/incidents/1/status"),
    ],
)
def test_manager_routes_require_a_token(
    client: TestClient, method: str, path: str
) -> None:
    call = getattr(client, method)
    kwargs = {"headers": {"Authorization": ""}}
    response = (
        call(path, **kwargs)
        if method == "get"
        else call(path, json={}, **kwargs)
    )
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# Seed — the CONTEXT expected values
# ---------------------------------------------------------------------------


CSV_PATH = Path(__file__).resolve().parents[3] / "scripts" / "incidents-trackflow.csv"


@pytest.fixture
def seeded(client: TestClient) -> TestClient:
    import sys

    scripts_dir = str(CSV_PATH.parent)
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)
    import seed_incidents

    seed_incidents.seed(CSV_PATH)
    return client


def test_seed_loads_the_95_valid_records(seeded: TestClient) -> None:
    assert len(seeded.get("/api/incidents").json()) == 95


def test_seed_rejects_the_5_invalid_rows(client: TestClient) -> None:
    import sys

    scripts_dir = str(CSV_PATH.parent)
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)
    import seed_incidents

    inserted, skipped, rejected, reasons = seed_incidents.seed(CSV_PATH)
    assert inserted == 95
    assert skipped == 0
    assert rejected == 5
    # Every rejection is accounted for by a reason, never silent.
    assert sum(reasons.values()) == 5


def test_seed_is_idempotent(client: TestClient) -> None:
    import sys

    scripts_dir = str(CSV_PATH.parent)
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)
    import seed_incidents

    seed_incidents.seed(CSV_PATH)
    inserted, skipped, _, _ = seed_incidents.seed(CSV_PATH)
    assert inserted == 0
    assert skipped == 95
    assert len(client.get("/api/incidents").json()) == 95


def test_seed_summary_matches_context_status_totals(seeded: TestClient) -> None:
    by_status = seeded.get("/api/incidents/summary").json()["by_status"]
    assert by_status["open"] == 29
    assert by_status["resolved"] == 52
    assert by_status["discarded"] == 14


def test_seed_summary_matches_context_category_totals(seeded: TestClient) -> None:
    by_category = seeded.get("/api/incidents/summary").json()["by_category"]
    assert by_category["lost_parcel"] == 14
    # DELAYED_DELIVERY (38) and DAMAGE (7) both fold into carrier_issue.
    assert by_category["carrier_issue"] == 45
    assert by_category["delivery_failure"] == 19
    assert by_category["returns_issue"] == 17


def test_every_seeded_record_is_customer_origin(seeded: TestClient) -> None:
    body = seeded.get("/api/incidents/summary").json()
    assert body["by_origin"]["customer"] == 95


def test_seed_maps_country_to_branch(seeded: TestClient) -> None:
    """CONTEXT: US -> la_office, ES -> zaragoza_office."""
    by_branch = seeded.get("/api/incidents/summary").json()["by_branch"]
    assert by_branch["la_office"] == 50
    assert by_branch["zaragoza_office"] == 45
    assert by_branch["central"] == 0


def test_seeded_titles_are_capped_at_120_chars(seeded: TestClient) -> None:
    for incident in seeded.get("/api/incidents").json():
        assert 0 < len(incident["title"]) <= 120


def test_seeded_timestamps_are_midnight_utc(seeded: TestClient) -> None:
    incident = seeded.get("/api/incidents").json()[0]
    assert incident["created_at"].endswith("+00:00")
    assert "T00:00:00" in incident["created_at"]
    # CONTEXT: updated_at matches created_at on insert.
    assert incident["updated_at"] == incident["created_at"]


# ---------------------------------------------------------------------------
# Registration cannot bypass the lifecycle
#
# Found by probing the create endpoint: it accepted a client-supplied
# `status`, so `POST {"status": "resolved"}` minted an incident directly
# into a final state — one no transition could ever leave, sitting in the
# CEO's summary as work that was never done.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("forbidden", ["resolved", "discarded", "in_progress"])
def test_cannot_register_an_incident_into_a_non_open_status(
    client: TestClient, forbidden: str
) -> None:
    r = client.post("/api/incidents", json={**VALID, "status": forbidden})
    assert r.status_code == 400, r.text
    detail = r.json()["detail"]
    assert detail["field"] == "status"
    assert "open" in detail["message"]


def test_registering_without_a_status_starts_open(client: TestClient) -> None:
    assert create(client)["status"] == "open"


def test_registering_with_an_explicit_open_status_is_accepted(
    client: TestClient,
) -> None:
    """Sending the correct value is not an error — only a wrong one is."""
    r = client.post("/api/incidents", json={**VALID, "status": "open"})
    assert r.status_code == 201, r.text
    assert r.json()["status"] == "open"


def test_a_final_status_is_unreachable_at_registration_time(
    client: TestClient,
) -> None:
    """The summary must never gain a resolved incident without a transition."""
    client.post("/api/incidents", json={**VALID, "status": "resolved"})
    assert client.get("/api/incidents/summary").json()["by_status"]["resolved"] == 0


# ---------------------------------------------------------------------------
# Concurrency
#
# TinyDB reads the whole JSON file, mutates it in memory, and writes it
# back, with no concurrency control. FastAPI runs sync handlers in a
# threadpool, so two simultaneous requests really do interleave those
# steps. Before `database` serialised access, the test below corrupted
# the file outright — every later read died with JSONDecodeError.
# ---------------------------------------------------------------------------


def test_concurrent_writes_do_not_corrupt_the_database(client: TestClient) -> None:
    import json
    from concurrent.futures import ThreadPoolExecutor

    from database import db_path

    def work(i: int) -> int:
        if i % 3 == 0:
            return client.post("/api/incidents", json={**VALID, "title": f"C{i}"}).status_code
        if i % 3 == 1:
            return client.get("/api/incidents").status_code
        return client.get("/api/incidents/summary").status_code

    with ThreadPoolExecutor(max_workers=16) as pool:
        codes = list(pool.map(work, range(60)))

    assert set(codes) <= {200, 201}, f"unexpected responses: {sorted(set(codes))}"

    # The file must still be valid JSON, not a truncated fragment.
    with db_path().open(encoding="utf-8") as handle:
        json.load(handle)

    expected = sum(1 for i in range(60) if i % 3 == 0)
    listed = client.get("/api/incidents").json()
    assert len([i for i in listed if i["title"].startswith("C")]) == expected
    # Interleaved inserts previously handed two rows the same document id.
    assert len({i["id"] for i in listed}) == len(listed)


def test_two_exclusive_final_transitions_cannot_both_succeed(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`resolved` and `discarded` are both final: exactly one must win.

    The check-then-write window is tight in normal operation, so this
    widens it deliberately — otherwise the test would pass even with the
    transaction removed and would guard nothing. With `db_transaction()`
    neutralised this fails on every run.
    """
    import time
    from concurrent.futures import ThreadPoolExecutor

    import routers.incidents_manager as manager

    real_now = manager._now_iso

    def slow_now() -> str:
        # Called between the transition check and the write.
        time.sleep(0.05)
        return real_now()

    monkeypatch.setattr(manager, "_now_iso", slow_now)

    incident_id = create(client)["id"]
    client.patch(f"/api/incidents/{incident_id}/status", json={"status": "in_progress"})

    with ThreadPoolExecutor(max_workers=2) as pool:
        codes = list(
            pool.map(
                lambda target: client.patch(
                    f"/api/incidents/{incident_id}/status", json={"status": target}
                ).status_code,
                ["resolved", "discarded"],
            )
        )

    assert codes.count(200) == 1, f"both transitions were accepted: {codes}"
    assert codes.count(400) == 1
    assert client.get(f"/api/incidents/{incident_id}").json()["status"] in {
        "resolved",
        "discarded",
    }
