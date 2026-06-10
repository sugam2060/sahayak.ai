from fastapi import WebSocket
import logging

logger = logging.getLogger("api_gateway.internal_chat.manager")

class InternalConnectionManager:
    def __init__(self):
        # Maps org_id -> list of (websocket, user_id)
        self.active_connections: dict[str, list[tuple[WebSocket, str]]] = {}

    async def connect(self, org_id: str, user_id: str, websocket: WebSocket) -> bool:
        try:
            from starlette.websockets import WebSocketState
            if websocket.client_state == WebSocketState.CONNECTING:
                await websocket.accept()
        except Exception:
            return False

        if org_id not in self.active_connections:
            self.active_connections[org_id] = []
        
        self.active_connections[org_id].append((websocket, str(user_id)))
        logger.info(f"[Internal WS] Connected user {user_id} for org {org_id}. Active count: {len(self.active_connections[org_id])}")
        return True

    def disconnect(self, org_id: str, websocket: WebSocket):
        if org_id in self.active_connections:
            for conn in self.active_connections[org_id]:
                if conn[0] == websocket:
                    self.active_connections[org_id].remove(conn)
                    logger.info(f"[Internal WS] Disconnected user {conn[1]} from org {org_id}.")
                    break
            if not self.active_connections[org_id]:
                del self.active_connections[org_id]

    async def broadcast_to_org(self, org_id: str, message: dict):
        """Broadcast message to all connected users in the organization."""
        if org_id in self.active_connections:
            for websocket, _ in self.active_connections[org_id]:
                try:
                    await websocket.send_json(message)
                except Exception as e:
                    logger.debug(f"[Internal WS] Failed to send broadcast message: {e}")

    async def broadcast_to_users(self, org_id: str, target_user_ids: list[str], message: dict):
        """Broadcast message only to a subset of connected users in the organization."""
        if org_id in self.active_connections:
            targets = [str(uid) for uid in target_user_ids]
            for websocket, user_id in self.active_connections[org_id]:
                if str(user_id) in targets:
                    try:
                        await websocket.send_json(message)
                    except Exception as e:
                        logger.debug(f"[Internal WS] Failed to send targeted message to {user_id}: {e}")

# Global instance
manager = InternalConnectionManager()
