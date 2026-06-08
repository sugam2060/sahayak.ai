import uuid
import logging
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID

from shared.database.engine import SessionLocal
from shared.database.schema.users import User
from services.api_gateway.routers.auth_routers.me import get_current_user
from services.api_gateway.routers.presence.presence_service import PresenceService
from services.api_gateway.routers.presence.presence_manager import presence_manager

logger = logging.getLogger("api_gateway.presence.router")
router = APIRouter(prefix="/api/presence", tags=["User Presence"])

# Dependency to get presence service instance
async def get_presence_service():
    return PresenceService()

async def safe_close(websocket: WebSocket, code: int):
    try:
        from starlette.websockets import WebSocketState
        if websocket.client_state == WebSocketState.CONNECTING:
            await websocket.accept()
        if websocket.client_state == WebSocketState.CONNECTED:
            await websocket.close(code=code)
    except Exception:
        pass

@router.websocket("/ws/{org_id}")
async def websocket_presence_endpoint(
    websocket: WebSocket,
    org_id: str,
    user_id: Optional[str] = None,
    device_type: str = "web",
    presence_service: PresenceService = Depends(get_presence_service)
):
    if not user_id:
        await safe_close(websocket, 4003)
        return

    async with SessionLocal() as db_session:
        # Validate user inside database
        try:
            user_stmt = select(User).where(User.id == UUID(user_id))
            user_result = await db_session.execute(user_stmt)
            db_user = user_result.scalar_one_or_none()
            if not db_user:
                logger.warning(f"[Presence WebSocket] User {user_id} not found in DB.")
                await safe_close(websocket, 4003)
                return
            
            if str(db_user.organization_id) != str(org_id):
                logger.warning(f"[Presence WebSocket] Organization mismatch. User organization: {db_user.organization_id}, requested: {org_id}")
                await safe_close(websocket, 4003)
                return
        except Exception as e:
            logger.error(f"[Presence WebSocket] Authorization DB error: {e}")
            await safe_close(websocket, 4003)
            return

    # User validated. Generate a unique socket_id
    socket_id = f"sock_{uuid.uuid4().hex}"
    
    # Connect to the manager (which also marks online in Redis and accepts connection)
    success = await presence_manager.connect(
        org_id=org_id,
        websocket=websocket,
        user_id=user_id,
        socket_id=socket_id,
        device_type=device_type
    )
    if not success:
        return

    try:
        while True:
            # Receive message as JSON
            data = await websocket.receive_json()
            event = data.get("event")
            
            if event == "presence:heartbeat":
                await presence_service.heartbeat(org_id, user_id, socket_id)
            elif event == "presence:status":
                status_val = data.get("status")
                # Allowed client status updates (cannot set to offline manually via presence:status)
                if status_val in ["online", "away", "busy"]:
                    await presence_service.set_status(org_id, user_id, status_val)
    except WebSocketDisconnect:
        await presence_manager.disconnect(org_id, websocket, user_id, socket_id)
    except Exception as e:
        logger.error(f"[Presence WebSocket] Connection error for user {user_id}: {e}")
        await presence_manager.disconnect(org_id, websocket, user_id, socket_id)

@router.get("/active")
async def get_active_users(
    within_seconds: int = 300,
    current_user: dict = Depends(get_current_user),
    presence_service: PresenceService = Depends(get_presence_service)
):
    org_id = current_user.get("organization_id")
    if not org_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User organization not found."
        )
    
    try:
        user_ids = await presence_service.get_org_online_users(org_id, within_seconds)
        statuses = await presence_service.get_bulk_status(org_id, user_ids)
        
        active_list = []
        for uid, status_data in statuses.items():
            if status_data:
                active_list.append({
                    "userId": uid,
                    "status": status_data["status"],
                    "lastSeen": status_data["lastSeen"],
                    "deviceType": status_data["deviceType"],
                    "activeTab": status_data["activeTab"],
                    "meta": status_data["meta"]
                })
        return {"success": True, "active": active_list}
    except Exception as e:
        logger.error(f"Failed to query active users: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to query active users: {str(e)}"
        )
