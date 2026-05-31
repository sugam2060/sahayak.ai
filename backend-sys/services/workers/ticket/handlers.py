import grpc
import logging
from uuid import UUID
from sqlalchemy import select, or_, and_
from shared.proto import service_pb2, service_pb2_grpc
from shared.database.engine import SessionLocal
from shared.database.schema.tickets import Ticket, TicketStatus, TicketPriority

logger = logging.getLogger("workers.tickets")

def to_ticket_info(ticket: Ticket) -> service_pb2.TicketInfo:
    return service_pb2.TicketInfo(
        id=str(ticket.id),
        organization_id=str(ticket.organization_id),
        title=ticket.title,
        description=ticket.description,
        status=ticket.status.value,
        priority=ticket.priority.value,
        customer_name=ticket.customer_name or "",
        customer_phone=ticket.customer_phone or "",
        assigned_agent_id=str(ticket.assigned_agent_id) if ticket.assigned_agent_id else "",
        created_at=ticket.created_at.isoformat() if ticket.created_at else "",
        updated_at=ticket.updated_at.isoformat() if ticket.updated_at else ""
    )

class TicketService(service_pb2_grpc.TicketServiceServicer):
    async def CreateTicket(self, request, context):
        try:
            org_id = UUID(request.organization_id)
            agent_id = UUID(request.assigned_agent_id) if request.assigned_agent_id else None
            
            try:
                status_enum = TicketStatus.OPEN
                priority_enum = TicketPriority(request.priority.lower())
            except ValueError:
                context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
                return service_pb2.CreateTicketResponse(success=False, message="Invalid priority.")

            async with SessionLocal() as db:
                ticket = Ticket(
                    organization_id=org_id,
                    title=request.title,
                    description=request.description,
                    status=status_enum,
                    priority=priority_enum,
                    customer_name=request.customer_name or None,
                    customer_phone=request.customer_phone or None,
                    assigned_agent_id=agent_id
                )
                db.add(ticket)
                await db.commit()
                await db.refresh(ticket)
                
                return service_pb2.CreateTicketResponse(
                    success=True,
                    ticket=to_ticket_info(ticket),
                    message="Ticket created successfully."
                )
        except Exception as e:
            logger.error(f"Error creating ticket in gRPC: {str(e)}", exc_info=True)
            context.set_code(grpc.StatusCode.INTERNAL)
            return service_pb2.CreateTicketResponse(success=False, message=str(e))

    async def ListTickets(self, request, context):
        try:
            org_id = UUID(request.organization_id)
            limit = request.limit if request.limit > 0 else 10
            cursor = request.cursor
            
            async with SessionLocal() as db:
                query = select(Ticket).where(Ticket.organization_id == org_id)
                
                # Filters
                if request.status:
                    try:
                        status_enum = TicketStatus(request.status.lower())
                        query = query.where(Ticket.status == status_enum)
                    except ValueError:
                        pass
                if request.priority:
                    try:
                        priority_enum = TicketPriority(request.priority.lower())
                        query = query.where(Ticket.priority == priority_enum)
                    except ValueError:
                        pass
                if request.search:
                    search_term = f"%{request.search}%"
                    query = query.where(
                        or_(
                            Ticket.title.ilike(search_term),
                            Ticket.description.ilike(search_term),
                            Ticket.customer_name.ilike(search_term),
                            Ticket.customer_phone.ilike(search_term)
                        )
                    )
                
                # Cursor pagination based on created_at + ID
                if cursor:
                    try:
                        cursor_uuid = UUID(cursor)
                        cursor_stmt = select(Ticket).where(Ticket.id == cursor_uuid)
                        cursor_res = await db.execute(cursor_stmt)
                        cursor_ticket = cursor_res.scalars().first()
                        if cursor_ticket:
                            query = query.where(
                                or_(
                                    Ticket.created_at < cursor_ticket.created_at,
                                    and_(
                                        Ticket.created_at == cursor_ticket.created_at,
                                        Ticket.id < cursor_uuid
                                    )
                                )
                            )
                    except ValueError:
                        pass
                
                query = query.order_by(Ticket.created_at.desc(), Ticket.id.desc()).limit(limit + 1)
                
                res = await db.execute(query)
                tickets = res.scalars().all()
                
                has_next = len(tickets) > limit
                if has_next:
                    tickets = tickets[:limit]
                    next_cursor = str(tickets[-1].id)
                else:
                    next_cursor = ""
                    
                ticket_infos = [to_ticket_info(t) for t in tickets]
                return service_pb2.ListTicketsResponse(
                    success=True,
                    tickets=ticket_infos,
                    next_cursor=next_cursor,
                    has_next=has_next
                )
        except Exception as e:
            logger.error(f"Error listing tickets in gRPC: {str(e)}", exc_info=True)
            context.set_code(grpc.StatusCode.INTERNAL)
            return service_pb2.ListTicketsResponse(success=False, message=str(e))

    async def GetTicketDetail(self, request, context):
        try:
            org_id = UUID(request.organization_id)
            ticket_id = UUID(request.ticket_id)
            
            async with SessionLocal() as db:
                stmt = select(Ticket).where(Ticket.id == ticket_id, Ticket.organization_id == org_id)
                res = await db.execute(stmt)
                ticket = res.scalars().first()
                
                if not ticket:
                    context.set_code(grpc.StatusCode.NOT_FOUND)
                    return service_pb2.GetTicketDetailResponse(success=False, message="Ticket not found.")
                    
                return service_pb2.GetTicketDetailResponse(
                    success=True,
                    ticket=to_ticket_info(ticket)
                )
        except Exception as e:
            logger.error(f"Error getting ticket detail in gRPC: {str(e)}", exc_info=True)
            context.set_code(grpc.StatusCode.INTERNAL)
            return service_pb2.GetTicketDetailResponse(success=False, message=str(e))

    async def UpdateTicket(self, request, context):
        try:
            org_id = UUID(request.organization_id)
            ticket_id = UUID(request.ticket_id)
            
            async with SessionLocal() as db:
                stmt = select(Ticket).where(Ticket.id == ticket_id, Ticket.organization_id == org_id)
                res = await db.execute(stmt)
                ticket = res.scalars().first()
                
                if not ticket:
                    context.set_code(grpc.StatusCode.NOT_FOUND)
                    return service_pb2.UpdateTicketResponse(success=False, message="Ticket not found.")
                
                if request.status:
                    try:
                        ticket.status = TicketStatus(request.status.lower())
                    except ValueError:
                        context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
                        return service_pb2.UpdateTicketResponse(success=False, message="Invalid status.")
                        
                if request.priority:
                    try:
                        ticket.priority = TicketPriority(request.priority.lower())
                    except ValueError:
                        context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
                        return service_pb2.UpdateTicketResponse(success=False, message="Invalid priority.")
                        
                await db.commit()
                await db.refresh(ticket)
                
                return service_pb2.UpdateTicketResponse(
                    success=True,
                    ticket=to_ticket_info(ticket),
                    message="Ticket updated successfully."
                )
        except Exception as e:
            logger.error(f"Error updating ticket in gRPC: {str(e)}", exc_info=True)
            context.set_code(grpc.StatusCode.INTERNAL)
            return service_pb2.UpdateTicketResponse(success=False, message=str(e))
