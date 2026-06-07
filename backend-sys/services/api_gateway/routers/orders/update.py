from fastapi import APIRouter, Depends, HTTPException, status, Request
from uuid import UUID
from pydantic import BaseModel, Field

from shared.proto import service_pb2
from services.api_gateway.routers.teams.permissions import check_permission

router = APIRouter(prefix="/api/orders")

class OrderStatusUpdate(BaseModel):
    status: str = Field(..., description="The next status of the order (pending, dispatch, delivered, cancelled)")

@router.put("/{order_id}/status")
async def update_order_status(
    order_id: UUID,
    req: OrderStatusUpdate,
    request: Request,
    current_user: dict = Depends(check_permission("orders"))
):
    try:
        grpc_req = service_pb2.UpdateOrderStatusRequest(
            organization_id=current_user["organization_id"],
            order_id=str(order_id),
            status=req.status
        )

        res = await request.app.state.order_stub.UpdateOrderStatus(grpc_req)

        if not res.success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=res.message or "Failed to update order status."
            )

        return {
            "success": True,
            "order_id": res.order_id,
            "status": res.status
        }

    except HTTPException as he:
        raise he
    except Exception as e:
        print(f"Error updating order status via gRPC: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update order status."
        )

