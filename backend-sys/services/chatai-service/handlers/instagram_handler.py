import logging
import httpx
from datetime import datetime, timezone
from shared.database.schema.chat_message_mongo import MessageDetail, MessageIntent
from .base_handler import BasePlatformHandler

logger = logging.getLogger("chatai_service.handlers.instagram")

class InstagramPlatformHandler(BasePlatformHandler):
    def __init__(self):
        super().__init__(platform="instagram")

    async def handle_inbound(self, event: dict) -> None:
        org_id = event.get("org_id")
        bot_name = event.get("bot_name")
        bot_token = event.get("bot_token")
        
        sender_id = event.get("sender_id")
        text = event.get("message_text", "")
        image_url = event.get("image_url")
        if not sender_id:
            logger.warning(f"Instagram DM event missing sender_id: {event}")
            return
        if not text and not image_url:
            logger.info("Instagram DM event has no text and no image_url. Skipping.")
            return
        
        # Instagram uses sender_id as chat_id
        chat_id = sender_id
        
        # Fetch Instagram user profile details from the Graph API
        sender_name = "Instagram User"
        sender_username = None
        profile_pic = None
        if bot_token:
            try:
                url = f"https://graph.instagram.com/v25.0/{sender_id}"
                params = {
                    "fields": "name,username,profile_pic",
                    "access_token": bot_token
                }
                async with httpx.AsyncClient() as client:
                    resp = await client.get(url, params=params, timeout=5.0)
                    if resp.status_code == 200:
                        profile_data = resp.json()
                        sender_name = (
                            profile_data.get("name")
                            or profile_data.get("username")
                            or "Instagram User"
                        )
                        sender_username = profile_data.get("username")
                        profile_pic = profile_data.get("profile_pic")
                        logger.info(f"Fetched Instagram profile for {sender_id}: name={sender_name}, username={sender_username}")
                    else:
                        logger.warning(f"Failed to fetch Instagram user profile: {resp.status_code} - {resp.text}")
            except Exception as e:
                logger.error(f"Error fetching Instagram user profile details: {e}", exc_info=True)

        sender_id_int = int(sender_id) if str(sender_id).isdigit() else None
        query_id = {"$in": [sender_id, sender_id_int]} if sender_id_int is not None else sender_id

        conv = await self.db.conversations.find_one({
            "platform": self.platform,
            "user.sender_id": query_id
        })
        
        actual_sender_id = conv["user"]["sender_id"] if conv else sender_id
        
        next_message_id = 1
        if conv and "messages" in conv:
            next_message_id = len(conv["messages"]) + 1
            
        inbound_msg = MessageDetail(
            message_id=next_message_id,
            direction="inbound",
            sender_id=actual_sender_id,
            sender_name=sender_name,
            text=text,
            image_url=image_url,
            intent=MessageIntent.NO_INTENT,
            created_at=datetime.now(timezone.utc)
        )
        
        user_data = {
            "sender_id": actual_sender_id,
            "sender_name": sender_name,
            "sender_username": sender_username,
            "profile_pic": profile_pic
        }
        
        now = datetime.now(timezone.utc)
        await self.db.conversations.update_one({
            "platform": self.platform,
            "user.sender_id": actual_sender_id
        }, {
            "$setOnInsert": {
                "organization_id": org_id,
                "bot_name": bot_name,
                "chat_id": chat_id,
                "ai_assigned": False,
                "created_at": now
            },
            "$set": {
                "user": user_data,
                "updated_at": now
            },
            "$push": {
                "messages": inbound_msg.model_dump()
            }
        }, upsert=True)

        logger.debug(f"Saved inbound message {next_message_id} from {sender_name} to MongoDB.")
        
        await self.broadcast_ws_event(
            org_id=org_id,
            sender_id=sender_id,
            event_type="new_message",
            extra_data={"message": inbound_msg.model_dump(mode="json")}
        )

    async def handle_outbound(self, event: dict) -> None:
        org_id = event.get("org_id")
        bot_name = event.get("bot_name")
        bot_token = event.get("bot_token")
        chat_id = event.get("chat_id")
        sender_id = event.get("sender_id")
        text = event.get("text", "")
        image_url = event.get("image_url")
        ig_account_id = event.get("ig_account_id") or "me"
        
        if not chat_id or not sender_id:
            logger.warning(f"Skipping outbound event missing chat_id or sender_id: {event}")
            return
        
        sender_id_int = int(sender_id) if str(sender_id).isdigit() else None
        query_id = {"$in": [sender_id, sender_id_int]} if sender_id_int is not None else sender_id

        conv = await self.db.conversations.find_one({
            "platform": self.platform,
            "user.sender_id": query_id
        })
        
        actual_sender_id = conv["user"]["sender_id"] if conv else sender_id
        
        next_message_id = 1
        if conv and "messages" in conv:
            next_message_id = len(conv["messages"]) + 1
        
        outbound_msg = MessageDetail(
            message_id=next_message_id,
            direction="outbound",
            sender_id=0,
            sender_name=bot_name,
            text=text,
            image_url=image_url,
            intent=MessageIntent.NO_INTENT,
            created_at=datetime.now(timezone.utc)
        )
        
        await self.db.conversations.update_one({
            "platform": self.platform,
            "user.sender_id": actual_sender_id
        }, {
            "$set": {"updated_at": datetime.now(timezone.utc)},
            "$push": {"messages": outbound_msg.model_dump()}
        })
        logger.debug(f"Saved outbound reply message {next_message_id} to MongoDB.")
        
        await self.broadcast_ws_event(
            org_id=org_id,
            sender_id=sender_id,
            event_type="new_message",
            extra_data={"message": outbound_msg.model_dump(mode="json")}
        )
        
        # Send reply via Instagram Graph API
        instagram_endpoint = f"https://graph.instagram.com/v25.0/{ig_account_id}/messages"
        try:
            async with httpx.AsyncClient() as client:
                payload = {
                    "recipient": {"id": sender_id},
                    "message": {"text": text}
                }
                if image_url:
                    payload["message"] = {"attachment": {"type": "image", "payload": {"url": image_url}}}
                logger.info(f"Sending Instagram DM reply to user {sender_id} via Graph API.")
                resp = await client.post(instagram_endpoint, json=payload, params={"access_token": bot_token}, timeout=5.0)
                if resp.status_code == 200:
                    logger.debug("Successfully sent Instagram DM reply.")
                else:
                    logger.error(f"Failed to send Instagram DM reply: {resp.status_code} - {resp.text}")
        except Exception as e:
            logger.error(f"Network error sending Instagram DM reply: {str(e)}")
