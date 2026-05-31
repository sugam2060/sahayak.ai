import logging
import httpx
from datetime import datetime, timezone
from shared.kafka_producer import KafkaProducerPool
from shared.database.mongodb import MongoDBManager
from shared.database.schema.chat_message_mongo import MessageDetail, MessageIntent

logger = logging.getLogger("chatai_service.chat_service")

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
    chat_id: int,
    sender_id: int,
    text: str,
    image_url: str = None
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
        "image_url": image_url
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
    Handles both inbound and outbound chat events consumed from Kafka, delegating AI and DB operations.
    """
    db = MongoDBManager.get_db()
    org_id = event.get("org_id")
    bot_name = event.get("bot_name")
    bot_token = event.get("bot_token")
    platform = event.get("platform", "telegram")
    direction = event.get("direction", "inbound")
    
    if direction == "inbound":
        payload = event.get("payload", {})
        # 1. Parse Telegram details
        message = payload.get("message", {})
        if not message:
            logger.info("Telegram payload has no message block. Skipping.")
            return
            
        chat = message.get("chat", {})
        sender = message.get("from", {})
        text = message.get("text") or message.get("caption") or ""
        image_url = message.get("image_url")
        
        chat_id = chat.get("id")
        sender_id = sender.get("id")
        if not chat_id or not sender_id:
            logger.warning(f"No chat_id or sender_id found in message: {message}")
            return
            
        sender_name = sender.get("first_name", "")
        if sender.get("last_name"):
            sender_name += " " + sender.get("last_name")
        sender_name = sender_name.strip() or "Unknown"
        sender_username = sender.get("username")
        
        # Find existing conversation to get current messages length and check if AI is assigned
        conv = await db.conversations.find_one({
            "platform": platform,
            "user.sender_id": sender_id
        })
        
        next_message_id = 1
        if conv and "messages" in conv:
            next_message_id = len(conv["messages"]) + 1
            
        # Create validated Inbound MessageDetail
        inbound_msg = MessageDetail(
            message_id=next_message_id,
            direction="inbound",
            sender_id=sender_id,
            sender_name=sender_name,
            text=text,
            image_url=image_url,
            intent=MessageIntent.NO_INTENT,
            created_at=datetime.now(timezone.utc)
        )
        
        # Get/Create the Conversation document
        user_data = {
            "sender_id": sender_id,
            "sender_name": sender_name,
            "sender_username": sender_username
        }
        
        now = datetime.now(timezone.utc)
        await db.conversations.update_one(
            {
                "platform": platform,
                "user.sender_id": sender_id
            },
            {
                "$setOnInsert": {
                    "organization_id": org_id,
                    "bot_name": bot_name,
                    "chat_id": chat_id,
                    "user": user_data,
                    "ai_assigned": False,
                    "created_at": now
                },
                "$set": {
                    "updated_at": now
                },
                "$push": {
                    "messages": inbound_msg.model_dump()
                }
            },
            upsert=True
        )
        logger.debug(f"Saved inbound message {next_message_id} from {sender_name} to MongoDB.")
        
        # Publish inbound message to Kafka chat_websocket topic
        try:
            ws_event = {
                "org_id": str(org_id),
                "platform": platform,
                "sender_id": sender_id,
                "type": "new_message",
                "message": inbound_msg.model_dump(mode="json")
            }
            await KafkaProducerPool.send_message("chat_websocket", ws_event)
            logger.debug(f"Published inbound message event to chat_websocket for org: {org_id}")
        except Exception as e:
            logger.error(f"Failed to publish inbound message to chat_websocket: {e}")
            
    elif direction == "outbound":
        chat_id = event.get("chat_id")
        sender_id = event.get("sender_id")
        text = event.get("text", "")
        image_url = event.get("image_url")
        
        if not chat_id or not sender_id:
            logger.warning(f"Skipping outbound event missing chat_id or sender_id: {event}")
            return
            
        # Find existing conversation
        conv = await db.conversations.find_one({
            "platform": platform,
            "user.sender_id": sender_id
        })
        
        next_message_id = 1
        if conv and "messages" in conv:
            next_message_id = len(conv["messages"]) + 1
            
        # Create validated Outbound MessageDetail
        outbound_msg = MessageDetail(
            message_id=next_message_id,
            direction="outbound",
            sender_id=0,  # Bot/System sender ID
            sender_name=bot_name,
            text=text,
            image_url=image_url,
            intent=MessageIntent.NO_INTENT,
            created_at=datetime.now(timezone.utc)
        )
        
        await db.conversations.update_one(
            {
                "platform": platform,
                "user.sender_id": sender_id
            },
            {
                "$set": {
                    "updated_at": datetime.now(timezone.utc)
                },
                "$push": {
                    "messages": outbound_msg.model_dump()
                }
            }
        )
        logger.debug(f"Saved outbound reply message {next_message_id} to MongoDB.")

        # Publish outbound message to Kafka chat_websocket topic
        try:
            ws_event = {
                "org_id": str(org_id),
                "platform": platform,
                "sender_id": sender_id,
                "type": "new_message",
                "message": outbound_msg.model_dump(mode="json")
            }
            await KafkaProducerPool.send_message("chat_websocket", ws_event)
            logger.debug(f"Published outbound message event to chat_websocket for org: {org_id}")
        except Exception as e:
            logger.error(f"Failed to publish outbound message to chat_websocket: {e}")
        
        # Send message back to Telegram user via Bot API
        from shared.config import TELEGRAM_API_BASE_URL
        try:
            async with httpx.AsyncClient() as client:
                if image_url:
                    telegram_url = f"{TELEGRAM_API_BASE_URL}/bot{bot_token}/sendPhoto"
                    tg_payload = {
                        "chat_id": chat_id,
                        "photo": image_url,
                    }
                    if text and text != "Shared a product card":
                        tg_payload["caption"] = text
                else:
                    telegram_url = f"{TELEGRAM_API_BASE_URL}/bot{bot_token}/sendMessage"
                    tg_payload = {
                        "chat_id": chat_id,
                        "text": text
                    }
                logger.info(f"Sending manual reply to Telegram chat {chat_id} via Bot API at {telegram_url}...")
                tg_response = await client.post(telegram_url, json=tg_payload, timeout=5.0)
                if tg_response.status_code == 200:
                    logger.debug("Successfully sent manual reply to Telegram user.")
                else:
                    logger.error(f"Failed to send manual reply to Telegram: {tg_response.status_code} - {tg_response.text}")
        except Exception as e:
            logger.error(f"Network error sending message to Telegram user: {str(e)}")

