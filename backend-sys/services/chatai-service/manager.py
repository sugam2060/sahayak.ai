import logging
from datetime import datetime, timezone
from shared.database.mongodb import MongoDBManager
from shared.kafka_producer import KafkaProducerPool
from .handlers import TelegramPlatformHandler, InstagramPlatformHandler

logger = logging.getLogger("chatai_service.manager")

class ChatServiceManager:
    def __init__(self):
        self.handlers = {
            "telegram": TelegramPlatformHandler(),
            "instagram": InstagramPlatformHandler(),
        }

    @property
    def db(self):
        return MongoDBManager.get_db()

    def get_handler(self, platform: str):
        handler = self.handlers.get(platform.lower())
        if not handler:
            raise ValueError(f"No platform handler registered for: {platform}")
        return handler

    async def handle_event(self, event: dict) -> None:
        direction = event.get("direction", "inbound")
        platform = event.get("platform", "telegram")
        event_type = event.get("event_type")

        if event_type == "seen":
            await self.handle_seen_event(event)
            return

        handler = self.get_handler(platform)
        if direction == "inbound":
            await handler.handle_inbound(event)
        elif direction == "outbound":
            await handler.handle_outbound(event)
        else:
            logger.warning(f"Unknown message direction: {direction} in event: {event}")

    async def handle_seen_event(self, event: dict) -> None:
        org_id = event.get("org_id")
        platform = event.get("platform", "telegram")
        sender_id = event.get("sender_id")
        watermark = event.get("watermark")
        if not sender_id or not watermark:
            logger.warning(f"Seen event missing sender_id or watermark: {event}")
            return
            
        watermark_dt = datetime.fromtimestamp(watermark / 1000.0, tz=timezone.utc)
        sender_id_int = int(sender_id) if str(sender_id).isdigit() else None
        query_id = {"$in": [sender_id, sender_id_int]} if sender_id_int is not None else sender_id
        
        conv = await self.db.conversations.find_one({
            "platform": platform,
            "user.sender_id": query_id
        })
        if not conv:
            logger.warning(f"No conversation found for seen event: platform={platform}, sender_id={sender_id}")
            return
            
        actual_sender_id = conv["user"]["sender_id"]
        updated = False
        messages = conv.get("messages", [])
        for msg in messages:
            if msg.get("direction") == "outbound" and not msg.get("seen"):
                msg_created = msg.get("created_at")
                if isinstance(msg_created, str):
                    try:
                        msg_dt = datetime.fromisoformat(msg_created.replace("Z", "+00:00"))
                    except Exception:
                        msg_dt = datetime.now(timezone.utc)
                elif isinstance(msg_created, datetime):
                    msg_dt = msg_created
                else:
                    msg_dt = datetime.now(timezone.utc)
                
                # Make msg_dt timezone-aware if it is naive
                if msg_dt.tzinfo is None:
                    msg_dt = msg_dt.replace(tzinfo=timezone.utc)
                
                if msg_dt <= watermark_dt:
                    msg["seen"] = True
                    updated = True
                    
        if updated:
            await self.db.conversations.update_one({
                "platform": platform,
                "user.sender_id": actual_sender_id
            }, {
                "$set": {
                    "messages": messages,
                    "updated_at": datetime.now(timezone.utc)
                }
            })
            
        try:
            ws_event = {
                "org_id": str(org_id),
                "platform": platform,
                "sender_id": actual_sender_id,
                "type": "chat_seen_update",
                "watermark": watermark
            }
            await KafkaProducerPool.send_message("chat_websocket", ws_event)
            logger.debug(f"Published seen update to chat_websocket: platform={platform}, sender_id={sender_id}")
        except Exception as e:
            logger.error(f"Failed to publish seen update to chat_websocket: {e}")
