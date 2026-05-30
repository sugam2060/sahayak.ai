from fastapi import APIRouter, HTTPException, status, Request
import json
import grpc
from uuid import UUID

from shared.proto import service_pb2
from shared.utils import decrypt_token
from shared.config import JWT_SECRET

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

@router.get("/track/{token}")
async def track_order(
    token: str,
    request: Request
):
    try:
        try:
            org_id, order_id = decrypt_token(token, JWT_SECRET)
        except Exception as decrypt_err:
            print(f"Decryption error for token {token}: {str(decrypt_err)}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Invalid tracking token or order not found."
            )

        grpc_req = service_pb2.GetOrderDetailsRequest(
            organization_id=org_id,
            order_id=order_id
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
        print(f"gRPC error during order tracking: {rpc_err.details()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve tracking details."
        )
    except Exception as e:
        print(f"Error fetching order tracking details: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve tracking details."
        )
