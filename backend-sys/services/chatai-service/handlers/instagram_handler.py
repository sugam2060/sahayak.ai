import logging
import httpx
from datetime import datetime, timezone
from shared.database.schema.chat_message_mongo import MessageDetail, MessageIntent
from .base_handler import BasePlatformHandler

logger = logging.getLogger("chatai_service.handlers.instagram")

def split_message(text: str, limit: int = 950) -> list[str]:
    """Split a message into chunks of at most limit characters, trying to split on newlines or spaces."""
    if not text:
        return []
    if len(text) <= limit:
        return [text]
    
    chunks = []
    while text:
        if len(text) <= limit:
            chunks.append(text)
            break
        
        # Try to find a good split point in the first 'limit' characters
        split_idx = text.rfind('\n', 0, limit)
        if split_idx == -1:
            split_idx = text.rfind(' ', 0, limit)
            
        if split_idx == -1 or split_idx == 0:
            # Force split if no space or newline is found
            split_idx = limit
            
        chunks.append(text[:split_idx])
        text = text[split_idx:].lstrip()
        
    return chunks

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
            "profile_pic": profile_pic
        }
        
        # Determine ai_assigned dynamically based on org config, active locks, and human assignment
        ai_enabled = await self._check_ai_enabled(org_id)
        if not ai_enabled:
            ai_assigned = False
        else:
            bot_id = conv.get("bot_id") if conv else None
            # If conversation is actively locked by a human user, AI is not assigned
            if bot_id and bot_id != "ai":
                ai_assigned = False
            else:
                # Check if any agents with chat permissions are online
                any_agent_online = await self._is_any_agent_online(org_id)
                if any_agent_online:
                    assigned_user = conv.get("assigned_user") if conv else None
                    if assigned_user:
                        ai_assigned = False
                    else:
                        # Respect manually toggled AI state if conversation exists, otherwise default to False
                        ai_assigned = conv.get("ai_assigned", False) if conv else False
                else:
                    # No agents online: AI auto reply takes over
                    ai_assigned = True
        
        now = datetime.now(timezone.utc)
        await self.db.conversations.update_one({
            "platform": self.platform,
            "user.sender_id": actual_sender_id
        }, {
            "$setOnInsert": {
                "organization_id": org_id,
                "bot_id": "ai" if ai_assigned else None,
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
                    ig_account_id=ig_account_id,
                )
                
                if ai_response:
                    if isinstance(ai_response, str):
                        text_reply = ai_response
                        image_urls = []
                        products = []
                    else:
                        text_reply = ai_response.get("text")
                        image_urls = ai_response.get("image_urls", [])
                        products = ai_response.get("products", [])
                    
                    if products:
                        for prod in products:
                            await route_outbound_reply(
                                org_id=org_id,
                                bot_name=bot_name,
                                bot_token=bot_token,
                                platform=self.platform,
                                chat_id=chat_id,
                                sender_id=actual_sender_id,
                                text="Shared a product card",
                                ig_account_id=ig_account_id,
                                message_type="product_card",
                                product_data=prod
                            )
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
                                ig_account_id=ig_account_id,
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
        
        assigned_user = event.get("assigned_user")
        message_type = event.get("message_type")
        product_data = event.get("product_data")

        outbound_msg = MessageDetail(
            message_id=next_message_id,
            direction="outbound",
            sender_id=0,
            sender_name=bot_name,
            text=cleaned_text,
            image_url=image_url,
            intent=MessageIntent.NO_INTENT,
            assigned_user=assigned_user,
            message_type=message_type,
            product_data=product_data,
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
        from uuid import UUID
        try:
            async with httpx.AsyncClient() as client:
                if message_type == "product_card" and product_data:
                    from types import SimpleNamespace
                    p = SimpleNamespace(**product_data)
                    
                    # Format Price
                    currency_upper = (p.currency or "NPR").upper()
                    symbol_map = {
                        "USD": "$", "EUR": "€", "GBP": "£", "INR": "₹",
                        "CAD": "CA$", "AUD": "A$", "JPY": "¥"
                    }
                    symbol = symbol_map.get(currency_upper, f"{currency_upper} ")
                    try:
                        val = float(p.price)
                        formatted_price = f"{val:,.2f}"
                    except Exception:
                        formatted_price = str(p.price)
                        
                    sent_successfully = False
                    if p.image:
                        # Construct native generic template payload
                        payload = {
                            "recipient": {"id": sender_id},
                            "message": {
                                "attachment": {
                                    "type": "template",
                                    "payload": {
                                        "template_type": "generic",
                                        "elements": [
                                            {
                                                "title": p.name[:79],
                                                "subtitle": f"{symbol}{formatted_price} · {p.description or ''}"[:79],
                                                "image_url": p.image
                                            }
                                        ]
                                    }
                                }
                            }
                        }
                        logger.info(f"Sending native Instagram generic template product card to user {sender_id}...")
                        resp = await client.post(instagram_endpoint, json=payload, params={"access_token": bot_token}, timeout=8.0)
                        if resp.status_code == 200:
                            sent_successfully = True
                            logger.debug("Successfully sent Instagram generic template.")
                        else:
                            logger.error(f"Failed to send Instagram generic template: {resp.status_code} - {resp.text}")
                            
                    # Trigger Pillow fallback if native send failed or image is missing
                    if not sent_successfully:
                        logger.info("Executing Pillow fallback for Instagram product card...")
                        from shared.redis_pool import RedisPool
                        import importlib
                        gen_card_module = importlib.import_module("services.chatai-service.ai.tools.products.generate_product_card")
                        _draw_pillow_card = gen_card_module._draw_pillow_card
                        
                        TEMPLATE_VERSION = "v1"
                        cache_key = f"product-card:{p.id}:{TEMPLATE_VERSION}"
                        redis_client = RedisPool.get_client()
                        
                        cached_url = await redis_client.get(cache_key)
                        if not cached_url:
                            # Retrieve organization name from DB
                            org_name = ""
                            try:
                                from shared.database.engine import SessionLocal
                                from shared.database.schema.organizations import Organization
                                from sqlalchemy import select
                                async with SessionLocal() as db_session:
                                    org_stmt = select(Organization.name).where(Organization.id == UUID(org_id))
                                    org_res = await db_session.execute(org_stmt)
                                    org_name = org_res.scalar() or ""
                            except Exception as db_err:
                                logger.error(f"Failed to fetch organization name for folder naming: {db_err}")
                                
                            img_bytes = _draw_pillow_card(p)
                            
                            from shared.utils import upload_cloudinary_image_bytes
                            img_url = await upload_cloudinary_image_bytes(
                                img_bytes,
                                f"card_{p.id}.png",
                                "image/png",
                                org_id,
                                org_name
                            )
                            if img_url:
                                cached_url = img_url
                                await redis_client.setex(cache_key, 86400, img_url)
                                
                        if cached_url:
                            payload = {
                                "recipient": {"id": sender_id},
                                "message": {"attachment": {"type": "image", "payload": {"url": cached_url}}}
                            }
                            resp = await client.post(instagram_endpoint, json=payload, params={"access_token": bot_token}, timeout=8.0)
                            if resp.status_code == 200:
                                logger.debug("Successfully sent fallback card photo to Instagram.")
                            else:
                                logger.error(f"Failed to send fallback photo to Instagram: {resp.status_code} - {resp.text}")
                        else:
                            # Final fallback: text only
                            payload = {
                                "recipient": {"id": sender_id},
                                "message": {"text": f"{p.name}\n💰 {symbol}{formatted_price}\n\n{p.description or ''}"}
                            }
                            await client.post(instagram_endpoint, json=payload, params={"access_token": bot_token}, timeout=8.0)

                elif image_url:
                    payload = {
                        "recipient": {"id": sender_id},
                        "message": {"attachment": {"type": "image", "payload": {"url": image_url}}}
                    }
                    logger.info(f"Sending Instagram image attachment to user {sender_id} via Graph API.")
                    resp = await client.post(instagram_endpoint, json=payload, params={"access_token": bot_token}, timeout=5.0)
                    if resp.status_code != 200:
                        logger.error(f"Failed to send Instagram image attachment: {resp.status_code} - {resp.text}")
 
                if text and text != "Shared a product card":
                    chunks = split_message(text, limit=950)
                    for idx, chunk in enumerate(chunks):
                        payload = {
                            "recipient": {"id": sender_id},
                            "message": {"text": chunk}
                        }
                        logger.info(f"Sending Instagram DM reply chunk {idx+1}/{len(chunks)} to user {sender_id} via Graph API.")
                        resp = await client.post(instagram_endpoint, json=payload, params={"access_token": bot_token}, timeout=5.0)
                        if resp.status_code != 200:
                            logger.error(f"Failed to send Instagram DM reply chunk {idx+1}: {resp.status_code} - {resp.text}")
        except Exception as e:
            logger.error(f"Network error sending Instagram DM reply: {str(e)}")
