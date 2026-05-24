import logging
import httpx
from datetime import datetime, timezone
from shared.kafka_producer import KafkaProducerPool
from shared.database.mongodb import MongoDBManager
from shared.database.schema.chat_message_mongo import MessageDetail, ConversationUser, ConversationMongo, MessageIntent

def detect_message_intent(text: str) -> MessageIntent:
    if not text:
        return MessageIntent.NO_INTENT
    keywords = ["buy", "price", "order", "cost", "purchase", "how much", "shop", "pay"]
    if any(keyword in text.lower() for keyword in keywords):
        return MessageIntent.BUY
    return MessageIntent.NO_INTENT

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
    text: str
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
        "text": text
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
        text = message.get("text", "")
        
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
            
        ai_assigned = conv.get("ai_assigned", False) if conv else False
        
        # Detect message intent
        intent_val = detect_message_intent(text)
        
        # Create validated Inbound MessageDetail
        inbound_msg = MessageDetail(
            message_id=next_message_id,
            direction="inbound",
            sender_id=sender_id,
            sender_name=sender_name,
            text=text,
            intent=intent_val,
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
            
        # If AI is assigned, perform automatic response
        if ai_assigned:
            from .ai.graph import invoke_customer_handling_graph
            from .ai.memory import compress_conversation_history

            try:
                ai_reply_text = await invoke_customer_handling_graph(
                    org_id=str(org_id),
                    platform=platform,
                    sender_id=sender_id,
                    bot_name=bot_name,
                    chat_id=chat_id,
                    user_message=text
                )
            except Exception as e:
                logger.error(f"Error invoking LangGraph workflow: {e}", exc_info=True)
                ai_reply_text = "I'm sorry, I encountered an error. A human agent will assist you shortly."

            # Fetch updated conversation to get correct message_id
            updated_conv = await db.conversations.find_one({
                "platform": platform,
                "user.sender_id": sender_id
            })
            next_outbound_id = len(updated_conv["messages"]) + 1 if updated_conv and "messages" in updated_conv else next_message_id + 1

            # Create validated Outbound MessageDetail
            outbound_msg = MessageDetail(
                message_id=next_outbound_id,
                direction="outbound",
                sender_id=0,  # Bot/System sender ID
                sender_name=bot_name,
                text=ai_reply_text,
                intent=MessageIntent.NO_INTENT,
                created_at=datetime.now(timezone.utc)
            )
            
            # Save outbound message to MongoDB
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
            logger.debug(f"Saved AI auto-reply outbound message {next_outbound_id} to MongoDB.")
            
            # Publish outbound message to Kafka chat_websocket topic
            try:
                ws_event_outbound = {
                    "org_id": str(org_id),
                    "platform": platform,
                    "sender_id": sender_id,
                    "type": "new_message",
                    "message": outbound_msg.model_dump(mode="json")
                }
                await KafkaProducerPool.send_message("chat_websocket", ws_event_outbound)
                logger.debug(f"Published AI auto-reply outbound event to chat_websocket for org: {org_id}")
            except Exception as e:
                logger.error(f"Failed to publish AI auto-reply to chat_websocket: {e}")
                
            # Send message back to Telegram user via Bot API
            async with httpx.AsyncClient() as client:
                telegram_url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
                tg_payload = {
                    "chat_id": chat_id,
                    "text": ai_reply_text
                }
                logger.debug(f"Sending AI auto-reply to Telegram chat {chat_id} via Bot API...")
                tg_response = await client.post(telegram_url, json=tg_payload, timeout=10.0)
                if tg_response.status_code == 200:
                    logger.debug("Successfully sent AI auto-reply to Telegram user.")
                else:
                    logger.error(f"Failed to send AI auto-reply to Telegram: {tg_response.status_code} - {tg_response.text}")
            
            # 8:6 memory compression check
            try:
                await compress_conversation_history(sender_id, platform)
            except Exception as e:
                logger.error(f"Failed to execute 8:6 memory compression: {e}", exc_info=True)
                    
    elif direction == "outbound":
        chat_id = event.get("chat_id")
        sender_id = event.get("sender_id")
        text = event.get("text", "")
        
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
        async with httpx.AsyncClient() as client:
            telegram_url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
            tg_payload = {
                "chat_id": chat_id,
                "text": text
            }
            logger.debug(f"Sending manual reply to Telegram chat {chat_id} via Bot API...")
            tg_response = await client.post(telegram_url, json=tg_payload, timeout=10.0)
            if tg_response.status_code == 200:
                logger.debug("Successfully sent manual reply to Telegram user.")
            else:
                logger.error(f"Failed to send manual reply to Telegram: {tg_response.status_code} - {tg_response.text}")
