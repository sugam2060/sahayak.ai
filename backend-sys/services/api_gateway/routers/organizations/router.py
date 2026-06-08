from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID

from shared.utils import get_db
from shared.redis_pool import RedisPool
from services.api_gateway.routers.teams.permissions import check_permission
from services.api_gateway.routers.organizations.schemas import OrganizationUpdate, OrganizationResponse
from services.api_gateway.routers.organizations.crud import OrganizationCRUD

router = APIRouter(prefix="/api/organizations", tags=["Organization Management"])

@router.get("/current", response_model=OrganizationResponse)
async def get_current_organization(
    current_user: dict = Depends(check_permission("org_settings")),
    db: AsyncSession = Depends(get_db)
):
    """
    Fetch the organization details for the currently authenticated session user.
    """
    try:
        org_id = UUID(current_user["organization_id"])
        org = await OrganizationCRUD.get_organization(db, org_id)
        if not org:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Organization not found."
            )
        return org
    except HTTPException as he:
        raise he
    except Exception as e:
        print(f"Error fetching current organization: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve organization details."
        )

@router.put("/current", response_model=OrganizationResponse)
async def update_current_organization(
    data: OrganizationUpdate,
    current_user: dict = Depends(check_permission("org_settings")),
    db: AsyncSession = Depends(get_db)
):
    """
    Update organization properties (e.g. name or slug).
    """
    try:
        org_id = UUID(current_user["organization_id"])
        updated_org = await OrganizationCRUD.update_organization(db, org_id, data)
        if not updated_org:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Organization not found."
            )
        return updated_org
    except ValueError as ve:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(ve)
        )
    except Exception as e:
        print(f"Error updating organization: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update organization."
        )

@router.delete("/current")
async def deactivate_current_organization(
    current_user: dict = Depends(check_permission("org_settings")),
    db: AsyncSession = Depends(get_db)
):
    """
    Soft-delete / deactivate the current organization and log out all users in it.
    """
    try:
        org_id = UUID(current_user["organization_id"])
        redis_client = RedisPool.get_client()
        
        success = await OrganizationCRUD.deactivate_organization(db, org_id, redis_client)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Organization not found."
            )
        return {
            "success": True,
            "message": "Organization deactivated successfully. All active sessions have been terminated."
        }
    except HTTPException as he:
        raise he
    except Exception as e:
        print(f"Error deactivating organization: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to deactivate organization."
        )
