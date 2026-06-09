from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from services.api_gateway.routers.account.crud import AccountService
from services.api_gateway.routers.account.schemas import (
    AccountProfileResponse,
    RequestEmailChangeRequest,
    UpdateNameRequest,
    UpdatePasswordRequest,
)
from services.api_gateway.routers.auth_routers.me import get_current_user
from shared.utils import get_db

router = APIRouter(prefix="/api/account", tags=["Account"])


@router.get("/profile", response_model=AccountProfileResponse)
async def get_account_profile(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve the authenticated user's full account profile."""
    user = await AccountService.get_profile(db, current_user["user_id"])
    return AccountProfileResponse(
        user_id=str(user.id),
        full_name=user.full_name,
        email=user.email,
        role=user.role.value if hasattr(user.role, "value") else str(user.role),
        created_at=user.created_at,
        last_login_at=user.last_login_at,
    )


@router.patch("/name")
async def update_name(
    body: UpdateNameRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update the authenticated user's display name."""
    await AccountService.update_name(db, current_user["user_id"], body.full_name)
    return {"success": True, "message": "Name updated successfully."}


@router.patch("/password")
async def update_password(
    body: UpdatePasswordRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Change the authenticated user's password.
    Requires the current password for verification before accepting the new one.
    """
    await AccountService.update_password(
        db,
        current_user["user_id"],
        body.current_password,
        body.new_password,
    )
    return {"success": True, "message": "Password updated successfully."}


@router.post("/email/request-change")
async def request_email_change(
    body: RequestEmailChangeRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Initiate an email address change.
    Sends a confirmation link to the NEW email address.
    The change is only applied after the link is clicked.
    """
    # Fetch name for personalised email
    user = await AccountService.get_profile(db, current_user["user_id"])
    await AccountService.request_email_change(
        db,
        current_user["user_id"],
        str(body.new_email),
        user.full_name,
    )
    return {
        "success": True,
        "message": f"Verification email sent to {body.new_email}. Please check your inbox.",
    }


@router.post("/email/confirm/{token}")
async def confirm_email_change(
    token: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Public endpoint — validates the email change token and applies the update.
    Returns a success message as JSON.
    """
    await AccountService.confirm_email_change(db, token)
    return {
        "success": True,
        "message": "Your email address has been verified and updated successfully.",
    }

