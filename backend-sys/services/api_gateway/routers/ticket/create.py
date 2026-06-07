from fastapi import APIRouter, Depends, HTTPException, status, Request
from uuid import UUID
from typing import Optional
from pydantic import BaseModel, Field
from shared.proto import service_pb2
from services.api_gateway.routers.teams.permissions import check_permission
from shared.utils import encrypt_token
from shared.config import JWT_SECRET

router = APIRouter(prefix="/api/tickets")

class TicketCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    description: str = Field(..., min_length=1)
    priority: str = Field("medium", description="low, medium, high, urgent")
    customer_name: Optional[str] = None
    customer_phone: Optional[str] = None
    assigned_agent_id: Optional[UUID] = None

@router.post("", status_code=status.HTTP_201_CREATED)
async def create_ticket(
    req: TicketCreate,
    request: Request,
    current_user: dict = Depends(check_permission("tickets"))
):
    try:
        grpc_req = service_pb2.CreateTicketRequest(
            organization_id=current_user["organization_id"],
            title=req.title.strip(),
            description=req.description.strip(),
            priority=req.priority.lower().strip(),
            customer_name=req.customer_name.strip() if req.customer_name else "",
            customer_phone=req.customer_phone.strip() if req.customer_phone else "",
            assigned_agent_id=str(req.assigned_agent_id) if req.assigned_agent_id else ""
        )
        
        res = await request.app.state.ticket_stub.CreateTicket(grpc_req)
        
        if not res.success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=res.message or "Failed to create ticket."
            )
            
        # Generate tracking token
        tracking_token = encrypt_token(
            org_id=current_user["organization_id"],
            order_id=res.ticket.id,
            secret=JWT_SECRET
        )
        
        return {
            "success": True,
            "ticket_id": res.ticket.id,
            "tracking_token": tracking_token,
            "message": "Ticket created successfully."
        }
    except HTTPException as he:
        raise he
    except Exception as e:
        print(f"Error creating ticket via gRPC: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create ticket. Please try again later."
        )
