"""
Tool: Place a new order for the customer via gRPC.
"""
import json
import logging
from typing import Annotated
from langchain_core.tools import tool
from langgraph.prebuilt import InjectedState
from shared.proto import service_pb2
from ...grpc_client import WorkersGRPCClient

logger = logging.getLogger("chatai_service.ai.tools.orders.place_order")


@tool
async def place_order(
    organization_id: Annotated[str, InjectedState("organization_id")],
    platform: Annotated[str, InjectedState("platform")],
    external_customer_id: Annotated[str, InjectedState("sender_id")],
    customer_name: Annotated[str, InjectedState("customer_name")],
    items: list[dict],
    customer_phone: str = "",
    delivery_address: str = "",
    currency: str = "NPR"
) -> str:
    """Place a new order for the customer. Use when a customer confirms they want to buy products.
    
    Args:
        organization_id: The organization's UUID (injected from state).
        platform: The platform name (injected from state).
        external_customer_id: The customer's platform-specific ID (injected from state).
        customer_name: The customer's profile name (injected from state).
        items: List of items to order. Each item is a dict with 'product_id' (str) and 'quantity' (int).
        customer_phone: Customer's phone number if provided.
        delivery_address: Delivery address if provided.
        currency: Currency code (default: NPR).
    """
    try:
        order_stub, _, _ = WorkersGRPCClient.get_stubs()
        
        order_items = [
            service_pb2.OrderItemCreateInput(
                product_id=item["product_id"],
                quantity=item.get("quantity", 1)
            )
            for item in items
        ]
        
        request = service_pb2.CreateOrderRequest(
            organization_id=organization_id,
            agent_id=organization_id,  # AI agent acts on behalf of the org
            platform=platform,
            external_customer_id=external_customer_id,
            customer_phone=customer_phone,
            delivery_address=delivery_address,
            currency=currency,
            items=order_items,
            customer_name=customer_name
        )
        
        response = await order_stub.CreateOrder(request)
        
        if response.success:
            from shared.config import FRONTEND_URL
            tracking_url = f"{FRONTEND_URL}/track-your-order/{response.tracking_token}"
            return (
                f"Order placed successfully!\n"
                f"Order ID: {response.order_id}\n"
                f"Total Amount: {response.total_amount} {currency}\n"
                f"Status: {response.status}\n"
                f"Tracking Link: {tracking_url}\n"
                f"Tracking Token: {response.tracking_token}"
            )
        else:
            return f"Failed to place order: {response.message}"
    except Exception as e:
        logger.error(f"Error placing order: {e}", exc_info=True)
        return f"Error placing order: {str(e)}"
