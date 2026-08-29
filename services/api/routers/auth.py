"""Authentication endpoints — login and whoami.

Stateless JWT only. POST /auth/login accepts either an OAuth2 form
(so Swagger UI's Authorize button works) or a JSON body.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import ValidationError

from database import users_table
from email_service import send_password_reset
from models import (
    ChangePasswordRequest,
    ForgotPasswordRequest,
    LoginRequest,
    MeOut,
    MessageResponse,
    ResetPasswordRequest,
    Token,
    UserInDB,
)
from password_reset import consume_token, invalidate_all_for_user, issue_token
from security import (
    access_token_expire_minutes,
    create_access_token,
    get_current_user,
    hash_password,
    verify_password,
)
from services_users import get_profile_by_user_id, get_user_by_email, get_user_by_id

logger = logging.getLogger("trackflow.auth")

router = APIRouter(prefix="/auth", tags=["auth"])

# One message for both "no such email" and "wrong password" — telling
# them apart lets an attacker enumerate registered accounts.
_BAD_CREDENTIALS = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Incorrect email or password",
    headers={"WWW-Authenticate": "Bearer"},
)


async def _read_credentials(request: Request) -> tuple[str, str]:
    """Pull (email, password) out of either accepted body shape.

    Swagger UI's Authorize dialog posts an OAuth2 form with `username`
    and `password`. The frontend posts JSON with `email` and
    `password`. Supporting both keeps the interactive docs usable
    without forcing the client into form encoding.
    """
    content_type = (request.headers.get("content-type") or "").lower()

    if content_type.startswith("application/json"):
        raw = await request.body()
        try:
            parsed = LoginRequest.model_validate_json(raw)
        except ValidationError as exc:
            # The message is fixed and derived from nothing in the
            # request. A Pydantic v2 error embeds the *input* it
            # rejected, so interpolating it here would return the
            # submitted password to the caller — and into the access log
            # — whenever the body was malformed.
            raise HTTPException(
                # 422 — the Starlette constant was renamed; the literal
                # keeps working across both naming eras.
                status_code=422,
                detail=(
                    "The sign-in request was malformed. It needs an email "
                    "and a password."
                ),
            ) from exc
        return parsed.email, parsed.password

    form = await request.form()
    email = str(form.get("username") or "").strip().lower()
    password = str(form.get("password") or "")
    return email, password


@router.post("/login", response_model=Token, summary="Log in, get a JWT")
async def login(request: Request) -> Token:
    """Validate credentials and return a signed access token."""
    email, password = await _read_credentials(request)

    if not email or not password:
        raise _BAD_CREDENTIALS

    user = get_user_by_email(email)
    if user is None or not verify_password(password, user.hashed_password):
        raise _BAD_CREDENTIALS

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="This account is deactivated.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = create_access_token(user_id=user.id, role=user.role)
    return Token(
        access_token=token,
        token_type="bearer",
        expires_in=access_token_expire_minutes() * 60,
    )


@router.get("/me", response_model=MeOut, summary="Who am I (protected)")
def read_me(caller: UserInDB = Depends(get_current_user)) -> MeOut:
    """Return the caller's credentials plus their linked profile."""
    return MeOut(
        id=caller.id,
        email=caller.email,
        role=caller.role,
        is_active=caller.is_active,
        profile=get_profile_by_user_id(caller.id),
    )


# ---------------------------------------------------------------------------
# Password reset / change (AUTH-03)
# ---------------------------------------------------------------------------

# One message for every outcome of /auth/forgot-password. Saying
# "no such account" would let anyone test which addresses are
# registered, so the response never varies.
_FORGOT_PASSWORD_MESSAGE = (
    "If that address is registered, you'll receive a link shortly."
)


@router.post(
    "/forgot-password",
    response_model=MessageResponse,
    summary="Request a password-reset link (always returns 200)",
)
def forgot_password(payload: ForgotPasswordRequest) -> MessageResponse:
    """Email a reset link to the address if it belongs to an account.

    Always 200, always the same body. The work below happens only when
    the user exists, but the caller cannot tell the difference.
    """
    user = get_user_by_email(payload.email)

    if user is not None and user.is_active:
        raw_token, ttl_minutes = issue_token(user.id)
        try:
            send_password_reset(user.email, raw_token, ttl_minutes)
        except Exception:
            # Deliberately broad, and deliberately here rather than only
            # inside the sender.
            #
            # This endpoint's security property is that its response never
            # varies — that is what stops it being an account-enumeration
            # oracle. The sender guards its own transport errors, but any
            # other failure (a misconfigured endpoint, a bug in the message
            # builder, an unexpected library error) used to escape and turn
            # a *registered* address into a 500 while an unknown address
            # still got 200. A provider incident would have handed an
            # attacker a working oracle.
            #
            # The property belongs to this route, so this route enforces
            # it. The reset token stays valid; the user can request another
            # link once delivery recovers.
            logger.exception("Password reset email could not be sent")

    return MessageResponse(message=_FORGOT_PASSWORD_MESSAGE)


@router.post(
    "/reset-password",
    response_model=MessageResponse,
    summary="Set a new password using a reset token",
)
def reset_password(payload: ResetPasswordRequest) -> MessageResponse:
    """Consume the token and set the new password.

    400 for a token that is unknown, expired, or already used — the
    three are reported identically so a caller cannot probe which
    tokens ever existed.
    """
    outcome = consume_token(payload.token)
    if not outcome.ok or outcome.user_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This reset link is invalid or has expired. Request a new one.",
        )

    user = get_user_by_id(outcome.user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This reset link is invalid or has expired. Request a new one.",
        )

    users_table().update(
        {"hashed_password": hash_password(payload.new_password)},
        doc_ids=[user.id],
    )
    # Any other outstanding link for this account dies with the reset.
    invalidate_all_for_user(user.id)

    return MessageResponse(
        message="Your password has been updated. You can now sign in."
    )


@router.post(
    "/change-password",
    response_model=MessageResponse,
    summary="Change your password while signed in (protected)",
)
def change_password(
    payload: ChangePasswordRequest,
    caller: UserInDB = Depends(get_current_user),
) -> MessageResponse:
    """Verify the current password, then set the new one."""
    if not verify_password(payload.current_password, caller.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Your current password is incorrect.",
        )

    users_table().update(
        {"hashed_password": hash_password(payload.new_password)},
        doc_ids=[caller.id],
    )
    # Changing the password should kill any reset link already in flight.
    invalidate_all_for_user(caller.id)

    return MessageResponse(message="Your password has been changed.")
