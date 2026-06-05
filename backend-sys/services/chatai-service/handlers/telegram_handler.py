import logging
import httpx
from datetime import datetime, timezone
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
        thread_id = f"{self.platform}:{sender_id}"
        conv = await self.db.conversations.find_one({"thread_id": thread_id})
        
        actual_sender_id = conv["user"]["sender_id"] if conv else sender_id
        is_new_conversation = conv is None
        
        user_data = {
            "sender_id": actual_sender_id,
            "sender_name": sender_name,
            "sender_username": sender_username,
            "profile_pic": None
        }
        
        # For new conversations, auto-set ai_assigned=True if org has AI enabled
        initial_ai_assigned = False
        if is_new_conversation:
            initial_ai_assigned = await self._check_ai_enabled(org_id)
        else:
            initial_ai_assigned = conv.get("ai_assigned", False)
        
        now = datetime.now(timezone.utc)
        await self.db.conversations.update_one({
            "thread_id": thread_id
        }, {
            "$setOnInsert": {
                "organization_id": org_id,
                "bot_name": bot_name,
                "chat_id": chat_id,
                "platform": self.platform,
                "sender_id": actual_sender_id,
                "ai_assigned": initial_ai_assigned,
                "created_at": now
            },
            "$set": {
                "user": user_data,
                "updated_at": now
            }
        }, upsert=True)

        # Update checkpointer state if AI is NOT assigned
        if not initial_ai_assigned:
            from langchain_core.messages import HumanMessage
            from ..ai.graph import get_agent_graph
            
            inbound_msg_lc = HumanMessage(
                content=text,
                additional_kwargs={
                    "direction": "inbound",
                    "sender_id": str(actual_sender_id),
                    "sender_name": sender_name,
                    "created_at": now.isoformat(),
                    "seen": False
                }
            )
            graph = get_agent_graph(self.db)
            config = {"configurable": {"thread_id": thread_id}}
            await graph.aupdate_state(config, {"messages": [inbound_msg_lc]})

        logger.debug(f"Saved inbound message from {sender_name} to checkpointer.")
        
        inbound_msg_dict = {
            "message_id": 0,
            "direction": "inbound",
            "sender_id": actual_sender_id,
            "sender_name": sender_name,
            "text": text,
            "image_url": image_url,
            "seen": False,
            "created_at": now.isoformat()
        }
        await self.broadcast_ws_event(
            org_id=org_id,
            sender_id=sender_id,
            event_type="new_message",
            extra_data={"message": inbound_msg_dict}
        )
        
        # --- AI Agent Invocation ---
        # Re-fetch conversation to get the latest ai_assigned state
        updated_conv = await self.db.conversations.find_one({"thread_id": thread_id})
        
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
                    await route_outbound_reply(
                        org_id=org_id,
                        bot_name=bot_name,
                        bot_token=bot_token,
                        platform=self.platform,
                        chat_id=chat_id,
                        sender_id=actual_sender_id,
                        text=ai_response,
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
        
        thread_id = f"{self.platform}:{sender_id}"
        conv = await self.db.conversations.find_one({"thread_id": thread_id})
        
        actual_sender_id = conv["user"]["sender_id"] if conv else sender_id
        
        # Deduplicate outbound replies: check if AI already saved this message to the checkpointer
        from ..ai.graph import get_agent_graph
        from langchain_core.messages import AIMessage
        
        graph = get_agent_graph(self.db)
        config = {"configurable": {"thread_id": thread_id}}
        state = await graph.aget_state(config)
        
        is_duplicate = False
        if state and "messages" in state.values and state.values["messages"]:
            last_msg = state.values["messages"][-1]
            if isinstance(last_msg, AIMessage) and last_msg.content == text:
                is_duplicate = True
                
        now = datetime.now(timezone.utc)
        if not is_duplicate:
            outbound_msg_lc = AIMessage(
                content=text,
                additional_kwargs={
                    "direction": "outbound",
                    "sender_id": 0,
                    "sender_name": bot_name or "Agent",
                    "created_at": now.isoformat(),
                    "seen": True
                }
            )
            await graph.aupdate_state(config, {"messages": [outbound_msg_lc]})
            
        await self.db.conversations.update_one(
            {"thread_id": thread_id},
            {"$set": {"updated_at": now}}
        )
        logger.debug("Saved outbound reply message to checkpointer.")
        
        outbound_msg_dict = {
            "message_id": 0,
            "direction": "outbound",
            "sender_id": 0,
            "sender_name": bot_name or "Agent",
            "text": text,
            "image_url": image_url,
            "seen": True,
            "created_at": now.isoformat()
        }
        await self.broadcast_ws_event(
            org_id=org_id,
            sender_id=sender_id,
            event_type="new_message",
            extra_data={"message": outbound_msg_dict}
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
