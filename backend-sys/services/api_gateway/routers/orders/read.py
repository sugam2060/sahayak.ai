from fastapi import APIRouter, Depends, HTTPException, status, Request
import grpc
from uuid import UUID

from shared.proto import service_pb2
from services.api_gateway.routers.auth_routers.me import get_current_user

router = APIRouter(prefix="/api/orders")

def proto_to_order_dict(o):
    return {
        "id": o.id,
        "platform": o.platform,
        "external_customer_id": o.external_customer_id if o.external_customer_id else None,
        "customer_phone": o.customer_phone if o.customer_phone else None,
        "delivery_address": o.delivery_address if o.delivery_address else None,
        "status": o.status,
        "total_amount": o.total_amount,
        "currency": o.currency,
        "assigned_agent_id": o.assigned_agent_id if o.assigned_agent_id else None,
        "created_at": o.created_at,
        "updated_at": o.updated_at,
        "tax_amount": o.tax_amount,
        "delivery_charge": o.delivery_charge,
        "items": [
            {
                "id": item.id,
                "product_id": item.product_id if item.product_id else None,
                "quantity": item.quantity,
                "unit_price": item.unit_price,
                "snapshot": json.loads(item.snapshot_json) if item.snapshot_json else {}
            }
            for item in o.items
        ]
    }

import json

@router.get("/{order_id}")
async def get_order_details(
    order_id: UUID,
    request: Request,
    current_user: dict = Depends(get_current_user)
):
    try:
        grpc_req = service_pb2.GetOrderDetailsRequest(
            organization_id=current_user["organization_id"],
            order_id=str(order_id)
        )
        res = await request.app.state.order_stub.GetOrderDetails(grpc_req)

        if not res.success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Order not found."
            )

        return {"success": True, "order": proto_to_order_dict(res.order)}

    except HTTPException as he:
        raise he
    except grpc.RpcError as rpc_err:
        if rpc_err.code() == grpc.StatusCode.NOT_FOUND:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Order not found."
            )
        print(f"gRPC error: {rpc_err.details()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve order details."
        )
    except Exception as e:
        print(f"Error fetching order details via gRPC: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve order details."
        )

@router.get("")
async def list_orders(
    request: Request,
    current_user: dict = Depends(get_current_user)
):
    try:
        grpc_req = service_pb2.ListOrdersRequest(
            organization_id=current_user["organization_id"]
        )
        res = await request.app.state.order_stub.ListOrders(grpc_req)

        if not res.success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to retrieve orders."
            )

        return {
            "success": True,
            "orders": [
                {
                    "id": o.id,
                    "platform": o.platform,
                    "external_customer_id": o.external_customer_id if o.external_customer_id else None,
                    "customer_phone": o.customer_phone if o.customer_phone else None,
                    "status": o.status,
                    "total_amount": o.total_amount,
                    "currency": o.currency,
                    "created_at": o.created_at
                }
                for o in res.orders
            ]
        }
    except Exception as e:
        print(f"Error listing orders via gRPC: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve orders."
        )

