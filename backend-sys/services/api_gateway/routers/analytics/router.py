from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID

from shared.utils import get_db
from services.api_gateway.routers.teams.permissions import check_permission
from services.api_gateway.routers.analytics.schemas import AnalyticsOverviewResponse
from services.api_gateway.routers.analytics.crud import AnalyticsService

router = APIRouter(prefix="/api/analytics", tags=["Analytics & Reports"])

@router.get("/overview", response_model=AnalyticsOverviewResponse)
async def get_analytics_overview(
    current_user: dict = Depends(check_permission("analytics")),
    db: AsyncSession = Depends(get_db)
):
    """
    Retrieve aggregated business sales and support ticket metrics.
    """
    try:
        org_id = UUID(current_user["organization_id"])
        metrics = await AnalyticsService.get_overview_metrics(db, org_id)
        return metrics
    except Exception as e:
        print(f"Error generating analytics overview: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to compile analytics metrics."
        )
