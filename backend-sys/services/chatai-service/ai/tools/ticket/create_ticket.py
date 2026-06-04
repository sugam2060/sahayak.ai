"""
Tool: Create a support ticket via gRPC.
"""
import logging
from typing import Annotated
from langchain_core.tools import tool
from langgraph.prebuilt import InjectedState
from shared.proto import service_pb2
from ...grpc_client import WorkersGRPCClient

logger = logging.getLogger("chatai_service.ai.tools.ticket.create_ticket")


@tool
async def create_support_ticket(
    organization_id: Annotated[str, InjectedState("organization_id")],
    title: str,
    description: str,
    priority: str = "medium",
    customer_name: str = "",
    customer_phone: str = ""
) -> str:
    """Create a new support ticket for the customer's issue.
    
    Args:
        organization_id: The organization's UUID (injected from state).
        title: Brief title describing the issue.
        description: Detailed description of the customer's problem.
        priority: Ticket priority. Valid values: low, medium, high, urgent.
        customer_name: Customer's name if known.
        customer_phone: Customer's phone number if provided.
    """
    try:
        _, _, ticket_stub = WorkersGRPCClient.get_stubs()
        
        request = service_pb2.CreateTicketRequest(
            organization_id=organization_id,
            title=title,
            description=description,
            priority=priority.lower(),
            customer_name=customer_name,
            customer_phone=customer_phone,
        )
        
        response = await ticket_stub.CreateTicket(request)
        
        if response.success and response.ticket:
            t = response.ticket
            return (
                f"Support ticket created successfully!\n"
                f"Ticket ID: {t.id}\n"
                f"Title: {t.title}\n"
                f"Status: {t.status}\n"
                f"Priority: {t.priority}"
            )
        else:
            return f"Failed to create ticket: {response.message}"
    except Exception as e:
        logger.error(f"Error creating ticket: {e}", exc_info=True)
        return f"Error creating support ticket: {str(e)}"
