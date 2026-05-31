from fastapi import APIRouter, Depends, HTTPException, status, Request
from uuid import UUID
from typing import Optional
from pydantic import BaseModel, Field
from shared.proto import service_pb2
from services.api_gateway.routers.auth_routers.me import get_current_user
from services.api_gateway.routers.ticket.read import ticket_to_dict

router = APIRouter(prefix="/api/tickets")

class TicketUpdate(BaseModel):
    status: Optional[str] = Field(None, description="open, in_progress, resolved, closed")
    priority: Optional[str] = Field(None, description="low, medium, high, urgent")

@router.put("/{ticket_id}")
async def update_ticket(
    ticket_id: UUID,
    req: TicketUpdate,
    request: Request,
    current_user: dict = Depends(get_current_user)
):
    try:
        org_id = current_user["organization_id"]
        grpc_req = service_pb2.UpdateTicketRequest(
            organization_id=org_id,
            ticket_id=str(ticket_id),
            status=req.status.strip() if req.status else "",
            priority=req.priority.strip() if req.priority else ""
        )
        
        res = await request.app.state.ticket_stub.UpdateTicket(grpc_req)
        
        if not res.success:
            raise HTTPException(
                status_code=400,
                detail=res.message or "Failed to update ticket."
            )
            
        return {
            "success": True,
            "ticket": ticket_to_dict(res.ticket, org_id),
            "message": "Ticket updated successfully."
        }
    except HTTPException as he:
        raise he
    except Exception as e:
        print(f"Error updating ticket via gRPC: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Failed to update ticket."
        )
