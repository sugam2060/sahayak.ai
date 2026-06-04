"""
Tool: List orders for the organization via gRPC.
"""
import json
import logging
from typing import Annotated
from langchain_core.tools import tool
from langgraph.prebuilt import InjectedState
from shared.proto import service_pb2
from ...grpc_client import WorkersGRPCClient

logger = logging.getLogger("chatai_service.ai.tools.orders.list_orders")


@tool
async def list_customer_orders(
    organization_id: Annotated[str, InjectedState("organization_id")],
    external_customer_id: Annotated[str, InjectedState("sender_id")]
) -> str:
    """List all orders for the current customer's account. Use to check their order history.
    
    Args:
        organization_id: The organization's UUID (injected from state).
        external_customer_id: The customer's platform-specific ID (injected from state).
    """
    try:
        order_stub, _, _ = WorkersGRPCClient.get_stubs()
        
        request = service_pb2.ListOrdersRequest(
            organization_id=organization_id
        )
        
        response = await order_stub.ListOrders(request)
        
        if response.success:
            # Filter orders to only show those belonging to the current customer
            customer_orders = [
                order for order in response.orders
                if str(order.external_customer_id) == str(external_customer_id)
            ]
            
            if not customer_orders:
                return "No orders found for your account."
            
            # Sort by creation date (or just take latest 10)
            order_lines = []
            for order in customer_orders[:10]:  # Limit to 10 most recent
                order_lines.append(
                    f"- Order {order.id}: Status={order.status}, "
                    f"Total={order.total_amount} {order.currency}, "
                    f"Created={order.created_at}"
                )
            
            result = f"Found {len(customer_orders)} orders (showing latest 10):\n"
            result += "\n".join(order_lines)
            return result
        else:
            return "Failed to retrieve orders."
    except Exception as e:
        logger.error(f"Error listing orders: {e}", exc_info=True)
        return f"Error listing orders: {str(e)}"
