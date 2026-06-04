"""
Tool: Update order status via gRPC.
"""
import logging
from typing import Annotated
from langchain_core.tools import tool
from langgraph.prebuilt import InjectedState
from shared.proto import service_pb2
from ...grpc_client import WorkersGRPCClient

logger = logging.getLogger("chatai_service.ai.tools.orders.update_order")


@tool
async def update_order_status(
    organization_id: Annotated[str, InjectedState("organization_id")],
    order_id: str,
    status: str
) -> str:
    """Update the status of an existing order.
    
    Args:
        organization_id: The organization's UUID (injected from state).
        order_id: The UUID of the order to update.
        status: New status. Valid values: pending, confirmed, processing, shipped, delivered, cancelled.
    """
    try:
        order_stub, _, _ = WorkersGRPCClient.get_stubs()
        
        request = service_pb2.UpdateOrderStatusRequest(
            organization_id=organization_id,
            order_id=order_id,
            status=status.lower()
        )
        
        response = await order_stub.UpdateOrderStatus(request)
        
        if response.success:
            return f"Order {response.order_id} status updated to: {response.status}"
        else:
            return f"Failed to update order status: {response.message}"
    except Exception as e:
        logger.error(f"Error updating order status: {e}", exc_info=True)
        return f"Error updating order status: {str(e)}"
