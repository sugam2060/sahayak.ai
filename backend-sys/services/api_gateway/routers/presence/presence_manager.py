import logging
from typing import Dict, List, Optional
from fastapi import WebSocket

logger = logging.getLogger("api_gateway.presence.manager")

class PresenceConnectionManager:
    def __init__(self, presence_service=None):
        from services.api_gateway.routers.presence.presence_service import PresenceService
        self.presence = presence_service or PresenceService()
        self.active_connections: Dict[str, List[WebSocket]] = {}

    async def connect(
        self,
        org_id: str,
        websocket: WebSocket,
        user_id: str,
        socket_id: str,
        device_type: str = "web"
    ) -> bool:
        try:
            from starlette.websockets import WebSocketState
            if websocket.client_state == WebSocketState.CONNECTING:
                await websocket.accept()
        except Exception as e:
            logger.error(f"[Presence WebSocket] Handshake failed: {e}")
            return False

        if org_id not in self.active_connections:
            self.active_connections[org_id] = []
        self.active_connections[org_id].append(websocket)

        # Update presence status to online in Redis
        try:
            await self.presence.set_online(
                org_id=org_id,
                user_id=user_id,
                socket_id=socket_id,
                device_type=device_type,
                status="online"
            )
        except Exception as e:
            logger.error(f"[Presence WebSocket] Failed to register online status in Redis: {e}")
        
        logger.info(f"[Presence WebSocket] Connected client {user_id} for org: {org_id}. Total active in org: {len(self.active_connections[org_id])}")
        return True

    async def disconnect(self, org_id: str, websocket: WebSocket, user_id: str, socket_id: str) -> None:
        if org_id in self.active_connections:
            if websocket in self.active_connections[org_id]:
                self.active_connections[org_id].remove(websocket)
            if not self.active_connections[org_id]:
                del self.active_connections[org_id]

        try:
            await self.presence.set_offline(org_id, user_id, socket_id)
        except Exception as e:
            logger.error(f"[Presence WebSocket] Failed to register offline status in Redis: {e}")

        logger.info(f"[Presence WebSocket] Disconnected client {user_id} from org {org_id}.")

    async def broadcast(self, org_id: str, message: dict) -> None:
        if org_id in self.active_connections:
            for connection in self.active_connections[org_id]:
                try:
                    await connection.send_json(message)
                except Exception as e:
                    logger.debug(f"[Presence WebSocket] Failed to send JSON message: {e}")

# Instantiate global manager
presence_manager = PresenceConnectionManager()
