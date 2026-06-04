"""
Tool: Cancel an order via gRPC.
"""
import logging
from typing import Annotated
from langchain_core.tools import tool
from langgraph.prebuilt import InjectedState
from shared.proto import service_pb2
from ...grpc_client import WorkersGRPCClient

logger = logging.getLogger("chatai_service.ai.tools.orders.cancel_order")


@tool
async def cancel_order(
    organization_id: Annotated[str, InjectedState("organization_id")],
    external_customer_id: Annotated[str, InjectedState("sender_id")],
    order_id: str
) -> str:
    """Cancel an existing order. Use when the customer requests cancellation.
    
    Args:
        organization_id: The organization's UUID (injected from state).
        external_customer_id: The customer's platform-specific ID (injected from state).
        order_id: The UUID of the order to cancel.
    """
    try:
        order_stub, _, _ = WorkersGRPCClient.get_stubs()
        
        # Verify ownership before cancelling
        details_req = service_pb2.GetOrderDetailsRequest(
            organization_id=organization_id,
            order_id=order_id
        )
        details_res = await order_stub.GetOrderDetails(details_req)
        if not details_res.success or not details_res.order:
            return f"Order not found with ID: {order_id}"
        
        if str(details_res.order.external_customer_id) != str(external_customer_id):
            return f"Order not found or access denied for ID: {order_id}"
        
        request = service_pb2.UpdateOrderStatusRequest(
            organization_id=organization_id,
            order_id=order_id,
            status="cancelled"
        )
        
        response = await order_stub.UpdateOrderStatus(request)
        
        if response.success:
            return f"Order {response.order_id} has been cancelled successfully."
        else:
            return f"Failed to cancel order: {response.message}"
    except Exception as e:
        logger.error(f"Error cancelling order: {e}", exc_info=True)
        return f"Error cancelling order: {str(e)}"
