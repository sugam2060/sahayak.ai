from fastapi import Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from shared.utils import get_db
from services.api_gateway.routers.auth_routers.me import get_current_user

def check_permission(permission_name: str):
    """
    FastAPI dependency to verify if the authenticated user has access to a specific resource.
    - OWNER role bypasses all restrictions.
    - ADMIN and AGENT roles must belong to a team that is assigned the required permission.
    """
    async def dependency(
        current_user: dict = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
    ):
        role = current_user.get("role", "").upper()
        if role == "OWNER":
            return current_user

        permissions = current_user.get("permissions", [])

        if permission_name not in permissions:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Your team lacks the '{permission_name}' permission."
            )
            
        return current_user

    return dependency

def require_owner():
    """
    FastAPI dependency to verify if the authenticated user has the OWNER role.
    """
    async def dependency(
        current_user: dict = Depends(get_current_user)
    ):
        role = current_user.get("role", "").upper()
        if role != "OWNER":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied. Organization owner role is required."
            )
        return current_user

    return dependency
