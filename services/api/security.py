"""Password hashing, JWT signing, and the auth dependencies.

Stateless JWT only — no sessions, no cookies. The token carries the
TinyDB user id in `sub`; every other module references that value as
`user_uuid`.

The signing secret and the token lifetime are read from the
environment, never hardcoded. See `.env.example`.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import jwt
from dotenv import load_dotenv
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

# libpass is a maintained drop-in fork of passlib; the import path is
# unchanged, which is why this reads as `passlib`.
from passlib.hash import bcrypt

from database import users_table
from models import Role, UserInDB

# The repository-root `.env` belongs to Docker Compose and may contain
# container-only paths such as `/workspace/...`. Native API development has a
# separate, documented environment file beside this module; never let dotenv
# walk upward and accidentally import Compose settings.
load_dotenv(Path(__file__).resolve().with_name(".env"))

ALGORITHM = "HS256"

# tokenUrl is what Swagger UI's Authorize button posts to.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")


# ---------------------------------------------------------------------------
# Settings — read at call time so tests can monkeypatch the environment
# ---------------------------------------------------------------------------


def secret_key() -> str:
    """The JWT signing secret.

    Deliberately has no default: a silent fallback would mean tokens
    signed with a publicly-known key, which is worse than failing to
    boot. Set SECRET_KEY in `.env`.
    """
    key = os.environ.get("SECRET_KEY", "").strip()
    if not key:
        raise RuntimeError(
            "SECRET_KEY is not set. Copy services/api/.env.example to "
            "services/api/.env and set a value "
            "(e.g. `python -c \"import secrets; print(secrets.token_hex(32))\"`)."
        )
    if len(key.encode()) < 32:
        raise RuntimeError(
            "SECRET_KEY must contain at least 32 bytes for HS256. Generate one "
            "with `python -c \"import secrets; print(secrets.token_hex(32))\"`."
        )
    return key


def access_token_expire_minutes() -> int:
    raw = os.environ.get("ACCESS_TOKEN_EXPIRE_MINUTES", "60").strip()
    try:
        return int(raw)
    except ValueError:
        return 60


# ---------------------------------------------------------------------------
# Passwords
# ---------------------------------------------------------------------------

# bcrypt truncates silently past 72 bytes. Rejecting longer input is
# better than storing a hash of a prefix the user never intended.
MAX_PASSWORD_BYTES = 72


def hash_password(plain: str) -> str:
    _guard_password_length(plain)
    return bcrypt.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.verify(plain, hashed)
    except (ValueError, TypeError):
        # Malformed stored hash — treat as a failed login, never a 500.
        return False


def _guard_password_length(plain: str) -> None:
    if len(plain.encode("utf-8")) > MAX_PASSWORD_BYTES:
        raise HTTPException(
            # 422 — the Starlette constant was renamed; the literal keeps
            # working across both naming eras.
            status_code=422,
            detail=(
                f"Password must be at most {MAX_PASSWORD_BYTES} bytes; "
                "bcrypt silently truncates beyond that."
            ),
        )


# ---------------------------------------------------------------------------
# Tokens
# ---------------------------------------------------------------------------


def create_access_token(
    user_id: int,
    role: Role,
    expires_delta: timedelta | None = None,
) -> str:
    """Sign a JWT carrying the TinyDB user id as `sub`."""
    expire = datetime.now(UTC) + (
        expires_delta or timedelta(minutes=access_token_expire_minutes())
    )
    claims: dict[str, Any] = {
        # `sub` must be a string per the JWT spec; callers cast back.
        "sub": str(user_id),
        "role": role.value,
        "exp": expire,
    }
    return jwt.encode(claims, secret_key(), algorithm=ALGORITHM)


def decode_token(token: str) -> dict[str, Any]:
    return jwt.decode(token, secret_key(), algorithms=[ALGORITHM])


# ---------------------------------------------------------------------------
# Dependencies
# ---------------------------------------------------------------------------

_CREDENTIALS_EXC = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Could not validate credentials",
    headers={"WWW-Authenticate": "Bearer"},
)


def get_current_user(token: str = Depends(oauth2_scheme)) -> UserInDB:
    """Decode the bearer token and return the caller.

    Raises 401 for a missing, malformed, expired, or wrongly-signed
    token, and for a token whose subject no longer exists or has been
    deactivated.
    """
    try:
        payload = decode_token(token)
    except jwt.PyJWTError:
        # Covers bad signature, expired `exp`, and structurally invalid tokens.
        raise _CREDENTIALS_EXC from None

    subject = payload.get("sub")
    if subject is None:
        raise _CREDENTIALS_EXC

    try:
        user_id = int(subject)
    except (TypeError, ValueError):
        raise _CREDENTIALS_EXC from None

    document = users_table().get(doc_id=user_id)
    if document is None:
        # Token was valid but the account is gone.
        raise _CREDENTIALS_EXC

    user = UserInDB(**{**document, "id": document.doc_id})
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="This account is deactivated.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


def require_self_or_admin(target_user_id: int, caller: UserInDB) -> None:
    """403 when a non-admin touches somebody else's record.

    Distinct from 401: the caller proved who they are, they just are
    not allowed to act on this resource.
    """
    if caller.role is Role.ADMIN:
        return
    if caller.id != target_user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You may only access your own account.",
        )
