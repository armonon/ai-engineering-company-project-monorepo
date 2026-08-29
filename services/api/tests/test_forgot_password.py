"""POST /auth/forgot-password.

Plan: TESTING.md § "POST /auth/forgot-password".

This endpoint's defining property is that it reveals nothing. Every test
below is really the same question asked from a different angle: can a
caller tell whether an address is registered?
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from tests.conftest import EMAIL

UNKNOWN = "nobody@trackflow.com"


def forgot(client: TestClient, email: str):
    return client.post("/auth/forgot-password", json={"email": email})


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


def test_a_registered_address_gets_exactly_one_reset_token(
    api: TestClient, registered: dict
) -> None:
    response = forgot(api, EMAIL)

    assert response.status_code == 200

    import database

    tokens = database.password_resets_table().all()
    assert len(tokens) == 1
    assert tokens[0]["user_id"] == registered["user"]["id"]
    assert tokens[0]["used_at"] is None


def test_only_a_hash_of_the_token_is_stored(api: TestClient, registered: dict) -> None:
    """A leak of the resets table must not yield usable reset links.

    The raw token exists only in the email; the row keeps its hash, the
    same way passwords are handled.
    """
    forgot(api, EMAIL)

    import database

    record = database.password_resets_table().all()[0]

    assert "token_hash" in record
    assert not any(key in record for key in ("token", "raw_token", "secret"))
    # A SHA-256 hex digest, not something reversible.
    assert len(record["token_hash"]) == 64
    int(record["token_hash"], 16)  # raises if it is not hex


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


def test_an_unknown_address_is_answered_identically_to_a_known_one(
    api: TestClient, registered: dict
) -> None:
    """Any observable difference — status, body, or a field — is an
    account-enumeration oracle."""
    known = forgot(api, EMAIL)
    unknown = forgot(api, UNKNOWN)

    assert known.status_code == unknown.status_code == 200
    assert known.json() == unknown.json()


def test_an_unknown_address_issues_no_token(api: TestClient, registered: dict) -> None:
    """Identical responses, but the work behind them differs."""
    forgot(api, UNKNOWN)

    import database

    assert database.password_resets_table().all() == []


def test_a_deactivated_account_issues_no_token_but_answers_the_same(
    api: TestClient, registered: dict
) -> None:
    import database

    database.users_table().update({"is_active": False}, doc_ids=[registered["user"]["id"]])

    response = forgot(api, EMAIL)

    assert response.status_code == 200
    assert database.password_resets_table().all() == []


def test_email_casing_does_not_change_the_outcome(
    api: TestClient, registered: dict
) -> None:
    """The address must be normalised the same way registration does, or a
    user who typed a capital letter silently gets no email."""
    response = forgot(api, EMAIL.upper())

    assert response.status_code == 200

    import database

    assert len(database.password_resets_table().all()) == 1


# ---------------------------------------------------------------------------
# Failure modes
# ---------------------------------------------------------------------------


def test_a_mail_delivery_failure_does_not_change_the_response(
    api: TestClient, registered: dict, monkeypatch
) -> None:
    """If a provider outage produced a different response, the endpoint
    would leak whether the address exists exactly when it is least able to
    tell anyone about it."""
    import routers.auth as auth_routes

    def explode(*_args, **_kwargs):
        raise RuntimeError("smtp is down")

    monkeypatch.setattr(auth_routes, "send_password_reset", explode)

    known = forgot(api, EMAIL)
    unknown = forgot(api, UNKNOWN)

    assert known.status_code == 200, known.text
    assert known.json() == unknown.json()


def test_requesting_a_second_link_kills_the_first(
    api: TestClient, registered: dict
) -> None:
    """Deliberate, and the safer of the two options.

    I first wrote this test expecting both links to stay live, which is
    what many products do. `issue_token` is explicit that it does the
    opposite: an old reset email left working is a live key to the
    account for as long as it sits in an inbox. Superseding is correct,
    so the test pins that instead.
    """
    forgot(api, EMAIL)
    forgot(api, EMAIL)

    import database

    tokens = database.password_resets_table().all()
    assert len(tokens) == 1, "the superseded token was left in the table"
    assert tokens[0]["used_at"] is None
