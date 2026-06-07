from fastapi import APIRouter, Depends, HTTPException, status, Request
from uuid import UUID
from typing import List, Optional
from pydantic import BaseModel, Field

from shared.proto import service_pb2
from services.api_gateway.routers.teams.permissions import check_permission

router = APIRouter(prefix="/api/orders")

class OrderItemCreate(BaseModel):
    product_id: UUID
    quantity: int = Field(..., gt=0)

class OrderCreate(BaseModel):
    platform: str = Field(..., description="e.g. telegram, chatbox, instagram")
    external_customer_id: Optional[str] = None
    customer_phone: str = Field(..., min_length=10, max_length=10)
    delivery_address: str = Field(..., min_length=1)
    currency: str = "NPR"
    items: List[OrderItemCreate]
    tax_percentage: Optional[int] = Field(0, description="Tax percentage (e.g. 13 for 13%)")
    delivery_charge: Optional[int] = Field(0, description="Delivery charge in subunits")
    customer_name: Optional[str] = None

@router.post("", status_code=status.HTTP_201_CREATED)
async def create_order(
    req: OrderCreate,
    request: Request,
    current_user: dict = Depends(check_permission("orders"))
):
    try:
        phone_stripped = req.customer_phone.strip()
        address_stripped = req.delivery_address.strip()
        if not phone_stripped or len(phone_stripped) != 10:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Customer phone number must be exactly 10 digits."
            )
        if not address_stripped:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Delivery address is required."
            )

        grpc_items = [
            service_pb2.OrderItemCreateInput(
                product_id=str(item.product_id),
                quantity=item.quantity
            )
            for item in req.items
        ]

        grpc_req = service_pb2.CreateOrderRequest(
            organization_id=current_user["organization_id"],
            agent_id=current_user["user_id"],
            platform=req.platform,
            external_customer_id=req.external_customer_id or "",
            customer_phone=phone_stripped,
            delivery_address=address_stripped,
            currency=req.currency,
            items=grpc_items,
            tax_percentage=req.tax_percentage or 0,
            delivery_charge=req.delivery_charge or 0,
            customer_name=req.customer_name or ""
        )

        res = await request.app.state.order_stub.CreateOrder(grpc_req)

        if not res.success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=res.message or "Failed to create order."
            )

        return {
            "success": True,
            "order_id": res.order_id,
            "total_amount": res.total_amount,
            "status": res.status,
            "tracking_token": res.tracking_token,
            "customer_id": res.customer_id
        }

    except HTTPException as he:
        raise he
    except Exception as e:
        print(f"Error creating order via gRPC: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create order. Please try again later."
        )

