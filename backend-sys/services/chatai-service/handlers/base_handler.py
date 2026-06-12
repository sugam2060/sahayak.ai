import logging
from abc import ABC, abstractmethod
from shared.database.mongodb import MongoDBManager
from shared.kafka_producer import KafkaProducerPool

logger = logging.getLogger("chatai_service.handlers.base")

class BasePlatformHandler(ABC):
    def __init__(self, platform: str):
        self.platform = platform

    @property
    def db(self):
        return MongoDBManager.get_db()

    async def _is_any_agent_online(self, org_id: str) -> bool:
        """Check if any agent with 'chats' permission is online for the organization."""
        try:
            from shared.database.engine import SessionLocal
            from shared.presence_service import get_eligible_online_users, PresenceService
            from shared.redis_pool import RedisPool

            redis_client = RedisPool.get_client()
            presence_service = PresenceService(redis_client)
            async with SessionLocal() as db_session:
                online_agents = await get_eligible_online_users(
                    org_id=org_id,
                    db=db_session,
                    presence_service=presence_service,
                    exclude_user_id=""
                )
            return len(online_agents) > 0
        except Exception as e:
            logger.error(f"Error checking online agents for org {org_id}: {e}", exc_info=True)
            return False

    @abstractmethod
    async def handle_inbound(self, event: dict) -> None:
        pass

    @abstractmethod
    async def handle_outbound(self, event: dict) -> None:
        pass

    async def broadcast_ws_event(self, org_id: str, sender_id: str, event_type: str, extra_data: dict) -> None:
        try:
            ws_event = {
                "org_id": str(org_id),
                "platform": self.platform,
                "sender_id": sender_id,
                "type": event_type,
            }
            ws_event.update(extra_data)
            await KafkaProducerPool.send_message("chat_websocket", ws_event)
            logger.debug(f"Published event {event_type} to chat_websocket for org: {org_id}")
        except Exception as e:
            logger.error(f"Failed to publish {event_type} to chat_websocket: {e}")
