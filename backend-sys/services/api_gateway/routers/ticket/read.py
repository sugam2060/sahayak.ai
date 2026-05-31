from fastapi import APIRouter, Depends, HTTPException, status, Request
from uuid import UUID
from typing import Optional
from shared.proto import service_pb2
from services.api_gateway.routers.auth_routers.me import get_current_user
from shared.utils import decrypt_token, encrypt_token
from shared.config import JWT_SECRET

router = APIRouter(prefix="/api/tickets")

def ticket_to_dict(ticket_info, org_id: str):
    tracking_token = encrypt_token(org_id, ticket_info.id, JWT_SECRET)
    return {
        "id": ticket_info.id,
        "organization_id": ticket_info.organization_id,
        "title": ticket_info.title,
        "description": ticket_info.description,
        "status": ticket_info.status,
        "priority": ticket_info.priority,
        "customer_name": ticket_info.customer_name,
        "customer_phone": ticket_info.customer_phone,
        "assigned_agent_id": ticket_info.assigned_agent_id,
        "created_at": ticket_info.created_at,
        "updated_at": ticket_info.updated_at,
        "tracking_token": tracking_token
    }

@router.get("")
async def list_tickets(
    request: Request,
    limit: int = 10,
    cursor: Optional[str] = None,
    status: Optional[str] = None,
    priority: Optional[str] = None,
    search: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    try:
        org_id = current_user["organization_id"]
        grpc_req = service_pb2.ListTicketsRequest(
            organization_id=org_id,
            limit=limit,
            cursor=cursor or "",
            status=status or "",
            priority=priority or "",
            search=search or ""
        )
        
        res = await request.app.state.ticket_stub.ListTickets(grpc_req)
        
        if not res.success:
            raise HTTPException(
                status_code=400,
                detail=res.message or "Failed to list tickets."
            )
            
        tickets_list = [ticket_to_dict(t, org_id) for t in res.tickets]
        return {
            "success": True,
            "tickets": tickets_list,
            "next_cursor": res.next_cursor,
            "has_next": res.has_next
        }
    except HTTPException as he:
        raise he
    except Exception as e:
        print(f"Error listing tickets via gRPC: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list tickets. Please try again later."
        )

@router.get("/track/{token}")
async def track_ticket(
    token: str,
    request: Request
):
    try:
        try:
            org_id, ticket_id = decrypt_token(token, JWT_SECRET)
        except Exception:
            raise HTTPException(
                status_code=400,
                detail="Invalid tracking token."
            )
            
        grpc_req = service_pb2.GetTicketDetailRequest(
            organization_id=org_id,
            ticket_id=ticket_id
        )
        
        res = await request.app.state.ticket_stub.GetTicketDetail(grpc_req)
        
        if not res.success:
            raise HTTPException(
                status_code=404,
                detail="Ticket not found."
            )
            
        return {
            "success": True,
            "ticket": ticket_to_dict(res.ticket, org_id)
        }
    except HTTPException as he:
        raise he
    except Exception as e:
        print(f"Error tracking ticket via gRPC: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Failed to track ticket."
        )

@router.get("/{ticket_id}")
async def get_ticket_detail(
    ticket_id: UUID,
    request: Request,
    current_user: dict = Depends(get_current_user)
):
    try:
        org_id = current_user["organization_id"]
        grpc_req = service_pb2.GetTicketDetailRequest(
            organization_id=org_id,
            ticket_id=str(ticket_id)
        )
        
        res = await request.app.state.ticket_stub.GetTicketDetail(grpc_req)
        
        if not res.success:
            raise HTTPException(
                status_code=404,
                detail="Ticket not found."
            )
            
        return {
            "success": True,
            "ticket": ticket_to_dict(res.ticket, org_id)
        }
    except HTTPException as he:
        raise he
    except Exception as e:
        print(f"Error fetching ticket detail via gRPC: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Failed to fetch ticket detail."
        )
