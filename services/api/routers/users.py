"""User CRUD — credentials only.

POST /users is the one public route here (registration). Everything
else requires a valid token, and acting on somebody else's account
requires the admin role.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status

from models import Role, UserCreate, UserInDB, UserOut, UserUpdate
from security import get_current_user, require_self_or_admin
from services_users import (
    create_user,
    delete_user,
    get_user_by_id,
    list_users,
    to_user_out,
    update_user,
)

router = APIRouter(prefix="/users", tags=["users"])


@router.post(
    "",
    response_model=UserOut,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user (public)",
)
def register_user(payload: UserCreate) -> UserOut:
    """Public registration.

    Hashes the password and creates the linked Profile in the same
    operation. The new account always gets the `user` role — a caller
    cannot self-assign `admin` by putting it in the body, because the
    field is not part of UserCreate at all.
    """
    return create_user(payload, role=Role.USER)


@router.get(
    "",
    response_model=list[UserOut],
    summary="List all users (protected)",
)
def get_users(_caller: UserInDB = Depends(get_current_user)) -> list[UserOut]:
    return list_users()


@router.get(
    "/{user_id}",
    response_model=UserOut,
    summary="Get a single user (protected)",
)
def get_user(
    user_id: int,
    caller: UserInDB = Depends(get_current_user),
) -> UserOut:
    require_self_or_admin(user_id, caller)
    user = get_user_by_id(user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No user with id {user_id}.",
        )
    return to_user_out(user)


@router.put(
    "/{user_id}",
    response_model=UserOut,
    summary="Update credential fields (protected; self or admin)",
)
def put_user(
    user_id: int,
    payload: UserUpdate,
    caller: UserInDB = Depends(get_current_user),
) -> UserOut:
    """Update email, password, active flag — and `role` for admins.

    A non-admin editing their own account may change their email and
    password but not their role; attempting it is a 403.
    """
    require_self_or_admin(user_id, caller)
    return update_user(user_id, payload, allow_role=caller.role is Role.ADMIN)


@router.delete(
    "/{user_id}",
    summary="Delete a user and their profile (protected; self or admin)",
)
def remove_user(
    user_id: int,
    caller: UserInDB = Depends(get_current_user),
) -> dict[str, Any]:
    require_self_or_admin(user_id, caller)
    return delete_user(user_id)
