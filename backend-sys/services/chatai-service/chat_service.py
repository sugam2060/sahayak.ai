import logging
from typing import Union
from shared.kafka_producer import KafkaProducerPool
from .manager import ChatServiceManager

logger = logging.getLogger("chatai_service.chat_service")

# Initialize orchestrator manager
_manager = ChatServiceManager()

async def route_telegram_message(org_id: str, bot_name: str, bot_token: str, payload: dict):
    """
    Produce the message event from Telegram Webhook and send it to the kafka chat_service topic.
    """
    message_event = {
        "org_id": org_id,
        "bot_name": bot_name,
        "bot_token": bot_token,
        "platform": "telegram",
        "direction": "inbound",
        "payload": payload
    }
    
    logger.info(f"Producing Telegram message event for org_id: {org_id} to chat_service topic.")
    try:
        # Publish message to Kafka topic 'chat_service'
        await KafkaProducerPool.send_message("chat_service", message_event)
        logger.info("Successfully produced message event to chat_service topic.")
    except Exception as e:
        logger.error(f"Failed to produce message event: {str(e)}")
        raise e

async def route_outbound_reply(
    org_id: str,
    bot_name: str,
    bot_token: str,
    platform: str,
    chat_id: Union[int, str],
    sender_id: Union[int, str],
    text: str,
    image_url: str = None,
    ig_account_id: str = None
):
    """
    Produce the outbound reply message event and send it to the kafka chat_service topic.
    """
    reply_event = {
        "org_id": org_id,
        "bot_name": bot_name,
        "bot_token": bot_token,
        "platform": platform,
        "direction": "outbound",
        "chat_id": chat_id,
        "sender_id": sender_id,
        "text": text,
        "image_url": image_url,
        "ig_account_id": ig_account_id
    }
    
    logger.info(f"Producing outbound reply event for sender_id: {sender_id} to chat_service topic.")
    try:
        # Publish message to Kafka topic 'chat_service'
        await KafkaProducerPool.send_message("chat_service", reply_event)
        logger.info("Successfully produced outbound reply event to chat_service topic.")
    except Exception as e:
        logger.error(f"Failed to produce outbound reply event: {str(e)}")
        raise e

async def handle_chat_event(event: dict):
    """
    Handles both inbound and outbound chat events consumed from Kafka by delegating to the manager.
    """
    try:
        await _manager.handle_event(event)
    except Exception as e:
        logger.error(f"Error handling event in manager: {e}", exc_info=True)
        raise e
