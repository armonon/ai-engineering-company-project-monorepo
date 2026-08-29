"""Profile endpoints.

Both routes are scoped to the authenticated caller — the profile is
resolved from the token, never from a client-supplied id, so there is
no way to read or edit somebody else's profile through this router.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from models import ProfileOut, ProfileUpdate, UserInDB
from security import get_current_user
from services_users import get_profile_by_user_id, update_profile

router = APIRouter(prefix="/profiles", tags=["profiles"])


@router.get(
    "/me",
    response_model=ProfileOut,
    summary="Get the authenticated user's profile (protected)",
)
def read_my_profile(caller: UserInDB = Depends(get_current_user)) -> ProfileOut:
    profile = get_profile_by_user_id(caller.id)
    if profile is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No profile is linked to this account.",
        )
    return profile


@router.put(
    "/me",
    response_model=ProfileOut,
    summary="Update the authenticated user's profile (protected)",
)
def update_my_profile(
    payload: ProfileUpdate,
    caller: UserInDB = Depends(get_current_user),
) -> ProfileOut:
    """Update name, phone, and address.

    Only the owner can reach this: the target is derived from the
    token's subject, so there is no id to tamper with.
    """
    return update_profile(caller.id, payload)
