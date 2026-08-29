"""Password reset / change tests (AUTH-03).

Email delivery is stubbed so no network call happens and the raw token
can be captured — the same token the user would receive by email.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

EMAIL = "carlos@trackflow.com"
PASSWORD = "original-password-1"


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("TINYDB_PATH", str(tmp_path / "reset.json"))
    monkeypatch.setenv("SECRET_KEY", "test-secret-not-a-real-one-32-bytes-minimum")
    monkeypatch.setenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60")
    monkeypatch.setenv("RESET_TOKEN_EXPIRE_MINUTES", "30")
    # No RESEND_API_KEY: the sender must never hit the network in tests.
    monkeypatch.delenv("RESEND_API_KEY", raising=False)

    import database

    database.close_db()

    from main import app

    with TestClient(app) as c:
        yield c

    database.close_db()


@pytest.fixture
def sent(monkeypatch: pytest.MonkeyPatch) -> list[dict]:
    """Capture reset emails instead of sending them."""
    import email_service
    import routers.auth as auth_routes

    box: list[dict] = []

    def fake_send(to_email: str, token: str, expires_minutes: int):
        box.append(
            {"to": to_email, "token": token, "expires_minutes": expires_minutes}
        )
        return email_service.SendResult(True, "test", "captured")

    # Patch the name the route actually calls.
    monkeypatch.setattr(auth_routes, "send_password_reset", fake_send)
    return box


def register(client: TestClient, email: str = EMAIL, password: str = PASSWORD) -> dict:
    r = client.post("/users", json={"email": email, "password": password})
    assert r.status_code == 201, r.text
    return r.json()


def login(client: TestClient, email: str, password: str):
    return client.post("/auth/login", json={"email": email, "password": password})


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def token_for(client: TestClient, email: str, password: str) -> str:
    r = login(client, email, password)
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


# ---------------------------------------------------------------------------
# forgot-password
# ---------------------------------------------------------------------------


def test_forgot_password_sends_a_link_for_a_registered_address(
    client: TestClient, sent: list[dict]
) -> None:
    register(client)
    r = client.post("/auth/forgot-password", json={"email": EMAIL})
    assert r.status_code == 200
    assert len(sent) == 1
    assert sent[0]["to"] == EMAIL
    assert sent[0]["token"]


def test_forgot_password_returns_200_for_an_unknown_address(
    client: TestClient, sent: list[dict]
) -> None:
    """No enumeration: an unregistered address gets the same 200."""
    register(client)
    r = client.post("/auth/forgot-password", json={"email": "nobody@trackflow.com"})
    assert r.status_code == 200
    # ...and no email is sent.
    assert sent == []


def test_forgot_password_response_is_identical_either_way(
    client: TestClient, sent: list[dict]
) -> None:
    register(client)
    known = client.post("/auth/forgot-password", json={"email": EMAIL})
    unknown = client.post("/auth/forgot-password", json={"email": "ghost@trackflow.com"})
    assert known.status_code == unknown.status_code == 200
    assert known.json() == unknown.json()


def test_forgot_password_rejects_a_malformed_email(client: TestClient) -> None:
    r = client.post("/auth/forgot-password", json={"email": "not-an-email"})
    assert r.status_code == 422


def test_requesting_a_second_link_invalidates_the_first(
    client: TestClient, sent: list[dict]
) -> None:
    """An older email must stop being a live key to the account."""
    register(client)
    client.post("/auth/forgot-password", json={"email": EMAIL})
    client.post("/auth/forgot-password", json={"email": EMAIL})
    first, second = sent[0]["token"], sent[1]["token"]

    stale = client.post(
        "/auth/reset-password", json={"token": first, "new_password": "new-password-1"}
    )
    assert stale.status_code == 400

    fresh = client.post(
        "/auth/reset-password", json={"token": second, "new_password": "new-password-1"}
    )
    assert fresh.status_code == 200


# ---------------------------------------------------------------------------
# reset-password
# ---------------------------------------------------------------------------


def test_reset_password_updates_the_password(
    client: TestClient, sent: list[dict]
) -> None:
    register(client)
    client.post("/auth/forgot-password", json={"email": EMAIL})

    r = client.post(
        "/auth/reset-password",
        json={"token": sent[0]["token"], "new_password": "a-brand-new-password"},
    )
    assert r.status_code == 200

    assert login(client, EMAIL, PASSWORD).status_code == 401           # old one dead
    assert login(client, EMAIL, "a-brand-new-password").status_code == 200


def test_a_token_cannot_be_used_twice(client: TestClient, sent: list[dict]) -> None:
    """The single-use requirement — the reason server-side state exists."""
    register(client)
    client.post("/auth/forgot-password", json={"email": EMAIL})
    token = sent[0]["token"]

    first = client.post(
        "/auth/reset-password", json={"token": token, "new_password": "first-new-pass"}
    )
    assert first.status_code == 200

    second = client.post(
        "/auth/reset-password", json={"token": token, "new_password": "second-new-pass"}
    )
    assert second.status_code == 400
    # The second attempt changed nothing.
    assert login(client, EMAIL, "first-new-pass").status_code == 200
    assert login(client, EMAIL, "second-new-pass").status_code == 401


def test_expired_token_is_rejected(client: TestClient, sent: list[dict]) -> None:
    register(client)
    client.post("/auth/forgot-password", json={"email": EMAIL})
    token = sent[0]["token"]

    # Age the stored record past its expiry.
    from datetime import UTC, datetime, timedelta

    from database import password_resets_table

    stale = (datetime.now(UTC) - timedelta(minutes=1)).isoformat()
    record = password_resets_table().all()[0]
    password_resets_table().update({"expires_at": stale}, doc_ids=[record.doc_id])

    r = client.post(
        "/auth/reset-password", json={"token": token, "new_password": "new-password-1"}
    )
    assert r.status_code == 400
    assert login(client, EMAIL, PASSWORD).status_code == 200  # unchanged


def test_unknown_token_is_rejected(client: TestClient) -> None:
    register(client)
    r = client.post(
        "/auth/reset-password",
        json={"token": "not-a-real-token", "new_password": "new-password-1"},
    )
    assert r.status_code == 400


def test_reset_rejects_a_short_password(client: TestClient, sent: list[dict]) -> None:
    register(client)
    client.post("/auth/forgot-password", json={"email": EMAIL})
    r = client.post(
        "/auth/reset-password", json={"token": sent[0]["token"], "new_password": "short"}
    )
    assert r.status_code == 422


def test_raw_token_is_never_stored(client: TestClient, sent: list[dict]) -> None:
    """Only the hash is persisted, so a DB leak is not a working link."""
    register(client)
    client.post("/auth/forgot-password", json={"email": EMAIL})
    raw = sent[0]["token"]

    from database import password_resets_table

    stored = password_resets_table().all()[0]
    assert stored["token_hash"] != raw
    assert raw not in str(stored)
    assert len(stored["token_hash"]) == 64  # sha256 hex


def test_invalid_and_expired_tokens_are_indistinguishable(
    client: TestClient, sent: list[dict]
) -> None:
    register(client)
    client.post("/auth/forgot-password", json={"email": EMAIL})
    used = sent[0]["token"]
    client.post(
        "/auth/reset-password", json={"token": used, "new_password": "new-password-1"}
    )

    replayed = client.post(
        "/auth/reset-password", json={"token": used, "new_password": "another-pass-1"}
    )
    unknown = client.post(
        "/auth/reset-password", json={"token": "garbage", "new_password": "another-pass-1"}
    )
    assert replayed.status_code == unknown.status_code == 400
    assert replayed.json()["detail"] == unknown.json()["detail"]


# ---------------------------------------------------------------------------
# change-password
# ---------------------------------------------------------------------------


def test_change_password_requires_a_session(client: TestClient) -> None:
    register(client)
    r = client.post(
        "/auth/change-password",
        json={"current_password": PASSWORD, "new_password": "new-password-1"},
    )
    assert r.status_code == 401


def test_change_password_succeeds_with_the_right_current_password(
    client: TestClient,
) -> None:
    register(client)
    token = token_for(client, EMAIL, PASSWORD)

    r = client.post(
        "/auth/change-password",
        json={"current_password": PASSWORD, "new_password": "changed-password-1"},
        headers=auth(token),
    )
    assert r.status_code == 200
    assert login(client, EMAIL, PASSWORD).status_code == 401
    assert login(client, EMAIL, "changed-password-1").status_code == 200


def test_change_password_rejects_a_wrong_current_password(
    client: TestClient,
) -> None:
    register(client)
    token = token_for(client, EMAIL, PASSWORD)

    r = client.post(
        "/auth/change-password",
        json={"current_password": "not-my-password", "new_password": "changed-pass-1"},
        headers=auth(token),
    )
    assert r.status_code == 400
    # Nothing changed.
    assert login(client, EMAIL, PASSWORD).status_code == 200


def test_change_password_rejects_a_short_new_password(client: TestClient) -> None:
    register(client)
    token = token_for(client, EMAIL, PASSWORD)
    r = client.post(
        "/auth/change-password",
        json={"current_password": PASSWORD, "new_password": "short"},
        headers=auth(token),
    )
    assert r.status_code == 422


def test_changing_the_password_kills_outstanding_reset_links(
    client: TestClient, sent: list[dict]
) -> None:
    """A link already sitting in an inbox must stop working."""
    register(client)
    client.post("/auth/forgot-password", json={"email": EMAIL})
    emailed_token = sent[0]["token"]

    token = token_for(client, EMAIL, PASSWORD)
    client.post(
        "/auth/change-password",
        json={"current_password": PASSWORD, "new_password": "changed-password-1"},
        headers=auth(token),
    )

    r = client.post(
        "/auth/reset-password",
        json={"token": emailed_token, "new_password": "hijacked-password"},
    )
    assert r.status_code == 400
    assert login(client, EMAIL, "hijacked-password").status_code == 401


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


def test_no_api_key_is_hardcoded() -> None:
    """The key must come from the environment, never the source.

    Matches the actual shape of a Resend key (`re_` + a long token)
    rather than the bare substring, which collides with ordinary
    identifiers like `expires_minutes`.
    """
    import re as _re

    import email_service

    source = Path(email_service.__file__).read_text(encoding="utf-8")
    assert not _re.search(r"re_[A-Za-z0-9]{16,}", source), "hardcoded Resend key"
    assert not _re.search(r"SG\.[A-Za-z0-9_\-]{16,}", source), "hardcoded SendGrid key"
    assert "os.environ" in source, "the key must be read from the environment"


def test_missing_api_key_falls_back_to_console_not_a_crash(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import email_service

    monkeypatch.delenv("RESEND_API_KEY", raising=False)
    result = email_service.send_password_reset("x@example.com", "tok", 30)
    assert result.delivered is False
    assert result.provider == "console"


def test_token_ttl_is_read_from_the_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import password_reset

    monkeypatch.setenv("RESET_TOKEN_EXPIRE_MINUTES", "45")
    assert password_reset.token_ttl_minutes() == 45

    # Clamped into a sane band: never unusable, never long-lived.
    monkeypatch.setenv("RESET_TOKEN_EXPIRE_MINUTES", "9999")
    assert password_reset.token_ttl_minutes() == 120
