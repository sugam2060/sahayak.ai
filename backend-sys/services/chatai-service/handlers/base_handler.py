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
