"""
Tool: List support tickets via gRPC.
"""
import logging
from typing import Annotated
from langchain_core.tools import tool
from langgraph.prebuilt import InjectedState
from shared.proto import service_pb2
from ...grpc_client import WorkersGRPCClient

logger = logging.getLogger("chatai_service.ai.tools.ticket.list_tickets")


@tool
async def list_tickets(
    organization_id: Annotated[str, InjectedState("organization_id")],
    status: str = "",
    limit: int = 10
) -> str:
    """List support tickets, optionally filtered by status.
    
    Args:
        organization_id: The organization's UUID (injected from state).
        status: Filter by status. Valid values: open, in_progress, resolved, closed. Leave empty for all.
        limit: Maximum number of tickets to return (default 10).
    """
    try:
        _, _, ticket_stub = WorkersGRPCClient.get_stubs()
        
        request = service_pb2.ListTicketsRequest(
            organization_id=organization_id,
            limit=limit,
            status=status.lower() if status else "",
        )
        
        response = await ticket_stub.ListTickets(request)
        
        if response.success:
            if not response.tickets:
                return "No tickets found."
            
            ticket_lines = []
            for t in response.tickets:
                ticket_lines.append(
                    f"- [{t.priority.upper()}] {t.title} (ID: {t.id})\n"
                    f"  Status: {t.status} | Customer: {t.customer_name or 'N/A'} | Created: {t.created_at}"
                )
            
            result = f"Found {len(response.tickets)} tickets:\n\n"
            result += "\n\n".join(ticket_lines)
            return result
        else:
            return "Failed to list tickets."
    except Exception as e:
        logger.error(f"Error listing tickets: {e}", exc_info=True)
        return f"Error listing tickets: {str(e)}"
