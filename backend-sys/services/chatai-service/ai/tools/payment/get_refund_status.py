"""
Tool: Get refund status for an order.
Stub — will be implemented when a payment gateway is integrated.
"""
from typing import Annotated
from langchain_core.tools import tool
from langgraph.prebuilt import InjectedState


@tool
async def get_refund_status(
    organization_id: Annotated[str, InjectedState("organization_id")],
    order_id: str
) -> str:
    """Check the refund status of an order. (Currently not available)
    
    Args:
        organization_id: The organization's UUID (injected from state).
        order_id: The order UUID to check refund status for.
    """
    return "Refund status tracking is not yet available. Please contact support for refund information."
