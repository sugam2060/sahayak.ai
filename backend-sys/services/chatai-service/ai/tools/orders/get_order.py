"""
Tool: Get order details via gRPC.
"""
import json
import logging
from typing import Annotated
from langchain_core.tools import tool
from langgraph.prebuilt import InjectedState
from shared.proto import service_pb2
from ...grpc_client import WorkersGRPCClient

logger = logging.getLogger("chatai_service.ai.tools.orders.get_order")


@tool
async def get_order_details(
    organization_id: Annotated[str, InjectedState("organization_id")],
    external_customer_id: Annotated[str, InjectedState("sender_id")],
    order_id: str
) -> str:
    """Get details of a specific order by its ID.
    
    Args:
        organization_id: The organization's UUID (injected from state).
        external_customer_id: The customer's platform-specific ID (injected from state).
        order_id: The UUID of the order to look up.
    """
    try:
        order_stub, _, _ = WorkersGRPCClient.get_stubs()
        
        request = service_pb2.GetOrderDetailsRequest(
            organization_id=organization_id,
            order_id=order_id
        )
        
        response = await order_stub.GetOrderDetails(request)
        
        if response.success and response.order:
            order = response.order
            
            # Enforce that the customer can only access their own orders
            if str(order.external_customer_id) != str(external_customer_id):
                return f"Order not found or access denied for ID: {order_id}"
            
            items_info = []
            for item in order.items:
                snapshot = json.loads(item.snapshot_json) if item.snapshot_json else {}
                items_info.append(
                    f"  - {snapshot.get('name', 'Unknown')} x{item.quantity} "
                    f"@ {item.unit_price} {order.currency}"
                )
            
            items_text = "\n".join(items_info) if items_info else "  No items"
            return (
                f"Order Details:\n"
                f"Order ID: {order.id}\n"
                f"Status: {order.status}\n"
                f"Total: {order.total_amount} {order.currency}\n"
                f"Tax: {order.tax_amount} {order.currency}\n"
                f"Delivery Charge: {order.delivery_charge} {order.currency}\n"
                f"Platform: {order.platform}\n"
                f"Created: {order.created_at}\n"
                f"Items:\n{items_text}"
            )
        else:
            return f"Order not found with ID: {order_id}"
    except Exception as e:
        logger.error(f"Error getting order details: {e}", exc_info=True)
        return f"Error retrieving order details: {str(e)}"
