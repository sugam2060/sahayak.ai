"""
Tool: Update a support ticket via gRPC.
"""
import logging
from typing import Annotated
from langchain_core.tools import tool
from langgraph.prebuilt import InjectedState
from shared.proto import service_pb2
from ...grpc_client import WorkersGRPCClient

logger = logging.getLogger("chatai_service.ai.tools.ticket.update_ticket")


@tool
async def update_ticket(
    organization_id: Annotated[str, InjectedState("organization_id")],
    ticket_id: str,
    status: str = "",
    priority: str = ""
) -> str:
    """Update the status or priority of a support ticket.
    
    Args:
        organization_id: The organization's UUID (injected from state).
        ticket_id: The UUID of the ticket to update.
        status: New status. Valid values: open, in_progress, resolved, closed. Leave empty to keep unchanged.
        priority: New priority. Valid values: low, medium, high, urgent. Leave empty to keep unchanged.
    """
    try:
        _, _, ticket_stub = WorkersGRPCClient.get_stubs()
        
        request = service_pb2.UpdateTicketRequest(
            organization_id=organization_id,
            ticket_id=ticket_id,
            status=status.lower() if status else "",
            priority=priority.lower() if priority else "",
        )
        
        response = await ticket_stub.UpdateTicket(request)
        
        if response.success and response.ticket:
            t = response.ticket
            return (
                f"Ticket updated successfully.\n"
                f"Ticket ID: {t.id}\n"
                f"Status: {t.status}\n"
                f"Priority: {t.priority}"
            )
        else:
            return f"Failed to update ticket: {response.message}"
    except Exception as e:
        logger.error(f"Error updating ticket: {e}", exc_info=True)
        return f"Error updating ticket: {str(e)}"
