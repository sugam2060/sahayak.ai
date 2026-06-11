import logging
from shared.kafka_producer import KafkaProducerPool

logger = logging.getLogger("chatai_service.ai.event_emitter")


class AIEventEmitter:
    """
    Helper utility to emit real-time AI events to the chat_websocket Kafka topic,
    which will be consumed and sent to WebSocket clients.
    """

    @staticmethod
    async def emit(org_id: str, platform: str, sender_id: str, event: str, status: str):
        try:
            ws_event = {
                "type": "ai_event",
                "org_id": str(org_id),
                "platform": platform,
                "sender_id": str(sender_id),
                "event": event,
                "status": status,
            }
            await KafkaProducerPool.send_message("chat_websocket", ws_event)
            logger.debug(f"Published AI event: {event} ({status}) to chat_websocket for org {org_id}")
        except Exception as e:
            logger.error(f"Failed to publish AI event {event} ({status}) to chat_websocket: {e}", exc_info=True)
