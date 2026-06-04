"""
Tool: Initiate a refund for an order.
Stub — will be implemented when a payment gateway is integrated.
"""
from typing import Annotated
from langchain_core.tools import tool
from langgraph.prebuilt import InjectedState


@tool
async def initiate_refund(
    organization_id: Annotated[str, InjectedState("organization_id")],
    order_id: str,
    reason: str = ""
) -> str:
    """Initiate a refund for an order. (Currently not available)
    
    Args:
        organization_id: The organization's UUID (injected from state).
        order_id: The order UUID to refund.
        reason: Reason for the refund.
    """
    return "Refund processing is not yet available. Please transfer the customer to a human agent for refund assistance."
