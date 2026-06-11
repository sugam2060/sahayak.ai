import logging
from typing import Union
from shared.kafka_producer import KafkaProducerPool

logger = logging.getLogger("chatai_service.handlers.router")

class ChatRouter:
    @staticmethod
    async def route_inbound(
        org_id: str,
        bot_name: str,
        bot_token: str,
        platform: str,
        payload: dict,
        event_type: str = "dm",
        **extra_fields
    ):
        """
        Generic inbound message routing for all social media platforms.
        """
        message_event = {
            "org_id": org_id,
            "bot_name": bot_name,
            "bot_token": bot_token,
            "platform": platform.lower(),
            "direction": "inbound",
            "event_type": event_type,
            "payload": payload
        }
        message_event.update(extra_fields)
        
        logger.info(f"Producing inbound {platform} event to chat_service Kafka topic.")
        try:
            await KafkaProducerPool.send_message("chat_service", message_event)
        except Exception as e:
            logger.error(f"Failed to produce inbound message event: {e}")
            raise e

    @staticmethod
    async def route_outbound(
        org_id: str,
        bot_name: str,
        bot_token: str,
        platform: str,
        chat_id: Union[int, str],
        sender_id: Union[int, str],
        text: str,
        image_url: str = None,
        ig_account_id: str = None,
        assigned_user: str = None,
        **kwargs
    ):
        """
        Generic outbound reply routing for all social media platforms.
        """
        reply_event = {
            "org_id": org_id,
            "bot_name": bot_name,
            "bot_token": bot_token,
            "platform": platform.lower(),
            "direction": "outbound",
            "chat_id": chat_id,
            "sender_id": sender_id,
            "text": text,
            "image_url": image_url,
            "ig_account_id": ig_account_id,
            "assigned_user": assigned_user
        }
        reply_event.update(kwargs)
        
        logger.info(f"Producing outbound {platform} reply to chat_service Kafka topic.")
        try:
            await KafkaProducerPool.send_message("chat_service", reply_event)
        except Exception as e:
            logger.error(f"Failed to produce outbound reply event: {e}")
            raise e
