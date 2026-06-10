import logging
import httpx
from datetime import datetime, timezone
from shared.database.schema.chat_message_mongo import MessageDetail, MessageIntent
from .base_handler import BasePlatformHandler

logger = logging.getLogger("chatai_service.handlers.telegram")

class TelegramPlatformHandler(BasePlatformHandler):
    def __init__(self):
        super().__init__(platform="telegram")

    async def _check_ai_enabled(self, org_id: str) -> bool:
        """Check if AI is enabled at the organization level."""
        try:
            from shared.database.engine import SessionLocal
            from shared.database.schema.organization_config_ai import OrganizationConfigAI
            from sqlalchemy import select
            from uuid import UUID
            
            async with SessionLocal() as db:
                stmt = select(OrganizationConfigAI).where(
                    OrganizationConfigAI.organization_id == UUID(org_id)
                )
                res = await db.execute(stmt)
                config = res.scalar_one_or_none()
                return config.ai_enabled if config else False
        except Exception as e:
            logger.error(f"Error checking AI enabled for org {org_id}: {e}")
            return False

    async def handle_inbound(self, event: dict) -> None:
        org_id = event.get("org_id")
        bot_name = event.get("bot_name")
        bot_token = event.get("bot_token")
        payload = event.get("payload", {})
        
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
            logger.warning(f"No chat_id or sender_id found in Telegram message: {message}")
            return
        
        sender_name = sender.get("first_name", "")
        if sender.get("last_name"):
            sender_name += " " + sender.get("last_name")
        sender_name = sender_name.strip() or "Unknown"
        sender_username = sender.get("username")

        # Find existing conversation
        sender_id_int = int(sender_id) if str(sender_id).isdigit() else None
        query_id = {"$in": [sender_id, sender_id_int]} if sender_id_int is not None else sender_id

        conv = await self.db.conversations.find_one({
            "platform": self.platform,
            "user.sender_id": query_id
        })
        
        actual_sender_id = conv["user"]["sender_id"] if conv else sender_id
        is_new_conversation = conv is None
        
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
            "profile_pic": None
        }
        
        # Determine ai_assigned dynamically based on org config and human assignment
        ai_enabled = await self._check_ai_enabled(org_id)
        assigned_user = conv.get("assigned_user") if conv else None
        ai_assigned = True if (ai_enabled and not assigned_user) else False
        
        now = datetime.now(timezone.utc)
        await self.db.conversations.update_one({
            "platform": self.platform,
            "user.sender_id": actual_sender_id
        }, {
            "$setOnInsert": {
                "organization_id": org_id,
                "bot_name": bot_name,
                "chat_id": chat_id,
                "created_at": now
            },
            "$set": {
                "user": user_data,
                "ai_assigned": ai_assigned,
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
        
        # --- AI Agent Invocation ---
        # Re-fetch conversation to get the latest ai_assigned state
        updated_conv = await self.db.conversations.find_one({
            "platform": self.platform,
            "user.sender_id": actual_sender_id
        })
        
        if updated_conv and updated_conv.get("ai_assigned"):
            try:
                from ..ai.agent import run_agent
                from ..chat_service import route_outbound_reply
                
                ai_response = await run_agent(
                    org_id=org_id,
                    platform=self.platform,
                    sender_id=actual_sender_id,
                    chat_id=chat_id,
                    bot_name=bot_name,
                    bot_token=bot_token,
                    inbound_text=text,
                    image_url=image_url,
                )
                
                if ai_response:
                    if isinstance(ai_response, str):
                        text_reply = ai_response
                        image_urls = []
                    else:
                        text_reply = ai_response.get("text")
                        image_urls = ai_response.get("image_urls", [])
                    
                    if image_urls:
                        for img_url in image_urls:
                            await route_outbound_reply(
                                org_id=org_id,
                                bot_name=bot_name,
                                bot_token=bot_token,
                                platform=self.platform,
                                chat_id=chat_id,
                                sender_id=actual_sender_id,
                                text="Shared a product card",
                                image_url=img_url,
                            )
                    if text_reply:
                        await route_outbound_reply(
                            org_id=org_id,
                            bot_name=bot_name,
                            bot_token=bot_token,
                            platform=self.platform,
                            chat_id=chat_id,
                            sender_id=actual_sender_id,
                            text=text_reply,
                        )
                        logger.info(f"AI agent replied to Telegram message from {sender_name}")
            except Exception as e:
                logger.error(f"AI agent error for Telegram {sender_id}: {e}", exc_info=True)

    async def handle_outbound(self, event: dict) -> None:
        org_id = event.get("org_id")
        bot_name = event.get("bot_name")
        bot_token = event.get("bot_token")
        chat_id = event.get("chat_id")
        sender_id = event.get("sender_id")
        text = event.get("text", "")
        image_url = event.get("image_url")
        
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
        
        from ..chat_service import remove_markdown
        cleaned_text = remove_markdown(text)
        
        outbound_msg = MessageDetail(
            message_id=next_message_id,
            direction="outbound",
            sender_id=0,
            sender_name=bot_name,
            text=cleaned_text,
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
        
        # Send message back to Telegram user via Bot API
        from shared.config import TELEGRAM_API_BASE_URL
        try:
            async with httpx.AsyncClient() as client:
                if image_url:
                    telegram_url = f"{TELEGRAM_API_BASE_URL}/bot{bot_token}/sendPhoto"
                    tg_payload = {"chat_id": chat_id, "photo": image_url}
                    if text and text != "Shared a product card":
                        tg_payload["caption"] = text
                else:
                    telegram_url = f"{TELEGRAM_API_BASE_URL}/bot{bot_token}/sendMessage"
                    tg_payload = {"chat_id": chat_id, "text": text}
                logger.info(f"Sending manual reply to Telegram chat {chat_id} via Bot API at {telegram_url}...")
                tg_response = await client.post(telegram_url, json=tg_payload, timeout=5.0)
                if tg_response.status_code == 200:
                    logger.debug("Successfully sent manual reply to Telegram user.")
                else:
                    logger.error(f"Failed to send manual reply to Telegram: {tg_response.status_code} - {tg_response.text}")
        except Exception as e:
            logger.error(f"Network error sending message to Telegram user: {str(e)}")
