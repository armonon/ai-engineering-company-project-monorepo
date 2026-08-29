"""JWT creation and validation, and GET /auth/me.

Plan: TESTING.md § "JWT creation and validation".

This is the module the outage came from: a refactor broke expiration and
nothing failed. So the expiry cases here test the *boundary* — one second
either side of `exp` — rather than a comfortable midpoint that would pass
even with the arithmetic wrong.

Most of these call `security` directly rather than going through HTTP.
The decision under test is "is this token acceptable", which is not an
HTTP question.
"""

from __future__ import annotations

import base64
import json
from datetime import UTC, datetime, timedelta

import jwt
import pytest
from fastapi.testclient import TestClient

from models import Role

SECRET = "test-secret-not-a-real-one-32-bytes-minimum"
ALGORITHM = "HS256"


def decode(token: str) -> dict:
    return jwt.decode(token, SECRET, algorithms=[ALGORITHM])


def me(api: TestClient, token: str):
    return api.get("/auth/me", headers={"Authorization": f"Bearer {token}"})


def _b64(payload: dict) -> str:
    """base64url of a JWT segment, without padding."""
    raw = json.dumps(payload, separators=(",", ":")).encode()
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


def test_a_fresh_token_resolves_to_the_user_who_owns_it(
    api: TestClient, registered: dict
) -> None:
    import security

    token = security.create_access_token(user_id=registered["user"]["id"], role=Role.USER)

    response = me(api, token)

    assert response.status_code == 200
    assert response.json()["id"] == registered["user"]["id"]


def test_the_subject_is_the_user_id_as_a_string(
    api: TestClient, registered: dict
) -> None:
    """JWT requires `sub` to be a string. Emitting an int works with some
    libraries and breaks others, which is exactly the kind of silent
    incompatibility this suite is meant to catch."""
    import security

    claims = decode(security.create_access_token(user_id=7, role=Role.USER))

    assert claims["sub"] == "7"
    assert isinstance(claims["sub"], str)


def test_expiry_is_taken_from_the_configured_lifetime(
    api: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The regression that started AUTH-088."""
    monkeypatch.setenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30")

    import security

    before = datetime.now(UTC)
    claims = decode(security.create_access_token(user_id=1, role=Role.USER))
    expires = datetime.fromtimestamp(claims["exp"], UTC)

    # Allow a couple of seconds for the clock to move during the call, but
    # nothing like enough to hide a wrong unit (30 seconds vs 30 minutes).
    assert timedelta(minutes=29, seconds=58) <= expires - before <= timedelta(minutes=30, seconds=2)


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


def test_a_token_one_second_before_expiry_is_still_accepted(
    api: TestClient, registered: dict
) -> None:
    import security

    token = security.create_access_token(
        user_id=registered["user"]["id"], role=Role.USER, expires_delta=timedelta(seconds=1)
    )

    assert me(api, token).status_code == 200


def test_a_token_one_second_past_expiry_is_rejected(
    api: TestClient, registered: dict
) -> None:
    """The other half of the boundary. A test that only used a long-expired
    token would pass even if the comparison were inverted at the edge."""
    import security

    token = security.create_access_token(
        user_id=registered["user"]["id"],
        role=Role.USER,
        expires_delta=timedelta(seconds=-1),
    )

    assert me(api, token).status_code == 401


@pytest.mark.parametrize("bad_value", ["not-a-number", "", "  ", "twelve"])
def test_an_unparseable_lifetime_falls_back_to_sixty_minutes(
    monkeypatch: pytest.MonkeyPatch, bad_value: str
) -> None:
    """A typo in the environment must not take authentication down."""
    monkeypatch.setenv("ACCESS_TOKEN_EXPIRE_MINUTES", bad_value)

    import security

    assert security.access_token_expire_minutes() == 60


# ---------------------------------------------------------------------------
# Failure modes — the attack surface
# ---------------------------------------------------------------------------


def test_an_unsigned_alg_none_token_is_rejected(
    api: TestClient, registered: dict
) -> None:
    """The classic JWT forgery: strip the signature and claim `alg: none`."""
    # The token is assembled by hand, which is how an attacker would produce it.
    header = _b64({"alg": "none", "typ": "JWT"})
    payload = _b64(
        {
            "sub": str(registered["user"]["id"]),
            "exp": int((datetime.now(UTC) + timedelta(hours=1)).timestamp()),
        }
    )
    forged = f"{header}.{payload}."   # empty signature

    assert me(api, forged).status_code == 401


def test_a_token_signed_with_another_secret_is_rejected(
    api: TestClient, registered: dict
) -> None:
    forged = jwt.encode(
        {
            "sub": str(registered["user"]["id"]),
            "exp": datetime.now(UTC) + timedelta(hours=1),
        },
        key="a-different-secret-entirely-but-long-enough-for-hs256",
        algorithm=ALGORITHM,
    )

    assert me(api, forged).status_code == 401


@pytest.mark.parametrize("subject", [None, "", "not-an-integer", "1.5"])
def test_a_token_without_a_usable_subject_is_rejected(
    api: TestClient, subject: object
) -> None:
    claims: dict = {"exp": datetime.now(UTC) + timedelta(hours=1)}
    if subject is not None:
        claims["sub"] = subject

    forged = jwt.encode(claims, key=SECRET, algorithm=ALGORITHM)

    assert me(api, forged).status_code == 401


def test_a_valid_token_for_a_deleted_account_is_rejected(
    api: TestClient, registered: dict
) -> None:
    """Signature valid, expiry fine, user gone. The token must stop
    working the moment the account does."""
    import database
    import security

    token = security.create_access_token(user_id=registered["user"]["id"], role=Role.USER)
    database.users_table().remove(doc_ids=[registered["user"]["id"]])

    assert me(api, token).status_code == 401


def test_a_valid_token_for_a_deactivated_account_is_rejected(
    api: TestClient, registered: dict
) -> None:
    import database
    import security

    token = security.create_access_token(user_id=registered["user"]["id"], role=Role.USER)
    database.users_table().update({"is_active": False}, doc_ids=[registered["user"]["id"]])

    response = me(api, token)

    assert response.status_code == 401
    assert "deactivated" in response.json()["detail"].lower()


def test_a_forged_admin_role_claim_does_not_grant_admin(
    api: TestClient, registered: dict
) -> None:
    """Privilege must come from the database row, not from the token.

    The token is attacker-supplied data; if the role were trusted from the
    claims, anyone could mint themselves an admin.
    """
    import security

    token = security.create_access_token(
        user_id=registered["user"]["id"], role=Role.ADMIN
    )

    response = me(api, token)

    assert response.status_code == 200
    assert response.json()["role"] == "user", "the token's role claim was trusted"


def test_a_structurally_broken_token_is_rejected_without_crashing(
    api: TestClient, registered: dict
) -> None:
    for rubbish in ["", "abc", "a.b.c", "....", "Bearer Bearer"]:
        assert me(api, rubbish).status_code == 401, f"{rubbish!r} was accepted"
