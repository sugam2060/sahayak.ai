import logging
import httpx
from datetime import datetime, timezone
from .base_handler import BasePlatformHandler

logger = logging.getLogger("chatai_service.handlers.instagram")

class InstagramPlatformHandler(BasePlatformHandler):
    def __init__(self):
        super().__init__(platform="instagram")

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
        
        sender_id = event.get("sender_id")
        text = event.get("message_text", "")
        image_url = event.get("image_url")
        ig_account_id = event.get("ig_account_id")
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

        # Find existing conversation
        thread_id = f"{self.platform}:{sender_id}"
        conv = await self.db.conversations.find_one({"thread_id": thread_id})
        
        actual_sender_id = conv["user"]["sender_id"] if conv else sender_id
        is_new_conversation = conv is None
        
        user_data = {
            "sender_id": actual_sender_id,
            "sender_name": sender_name,
            "sender_username": sender_username,
            "profile_pic": profile_pic
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
                    ig_account_id=ig_account_id,
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
                        ig_account_id=ig_account_id,
                    )
                    logger.info(f"AI agent replied to Instagram message from {sender_name}")
            except Exception as e:
                logger.error(f"AI agent error for Instagram {sender_id}: {e}", exc_info=True)

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
