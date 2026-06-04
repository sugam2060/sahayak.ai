"""
Tool: Get ticket details via gRPC.
"""
import logging
from typing import Annotated
from langchain_core.tools import tool
from langgraph.prebuilt import InjectedState
from shared.proto import service_pb2
from ...grpc_client import WorkersGRPCClient

logger = logging.getLogger("chatai_service.ai.tools.ticket.get_ticket")


@tool
async def get_ticket_detail(
    organization_id: Annotated[str, InjectedState("organization_id")],
    ticket_id: str
) -> str:
    """Get details of a specific support ticket.
    
    Args:
        organization_id: The organization's UUID (injected from state).
        ticket_id: The UUID of the ticket.
    """
    try:
        _, _, ticket_stub = WorkersGRPCClient.get_stubs()
        
        request = service_pb2.GetTicketDetailRequest(
            organization_id=organization_id,
            ticket_id=ticket_id
        )
        
        response = await ticket_stub.GetTicketDetail(request)
        
        if response.success and response.ticket:
            t = response.ticket
            return (
                f"Ticket Details:\n"
                f"ID: {t.id}\n"
                f"Title: {t.title}\n"
                f"Description: {t.description}\n"
                f"Status: {t.status}\n"
                f"Priority: {t.priority}\n"
                f"Customer: {t.customer_name or 'N/A'}\n"
                f"Phone: {t.customer_phone or 'N/A'}\n"
                f"Created: {t.created_at}"
            )
        else:
            return f"Ticket not found with ID: {ticket_id}"
    except Exception as e:
        logger.error(f"Error getting ticket: {e}", exc_info=True)
        return f"Error getting ticket details: {str(e)}"
