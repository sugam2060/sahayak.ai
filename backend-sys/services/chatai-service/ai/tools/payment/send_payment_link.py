"""
Tool: Send a payment link to the customer.
Stub — will be implemented when a payment gateway is integrated.
"""
from typing import Annotated
from langchain_core.tools import tool
from langgraph.prebuilt import InjectedState


@tool
async def send_payment_link(
    organization_id: Annotated[str, InjectedState("organization_id")],
    order_id: str,
    amount: int,
    currency: str = "NPR"
) -> str:
    """Send a payment link to the customer for an order. (Currently not available)
    
    Args:
        organization_id: The organization's UUID (injected from state).
        order_id: The order UUID to generate a payment link for.
        amount: The payment amount.
        currency: Currency code (default: NPR).
    """
    return "Payment link generation is not yet available. Please ask the customer to contact support for payment options."
