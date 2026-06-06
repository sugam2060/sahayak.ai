import logging
import json
import hmac
import hashlib
import httpx
import asyncio
import cloudinary
import cloudinary.uploader
from fastapi import APIRouter, Request, Depends, Response
from fastapi.responses import HTMLResponse, PlainTextResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from shared.database.engine import SessionLocal
from shared.database.schema.platform_connectors import PlatformConnector
from shared.config import (
    INSTAGRAM_VERIFY_TOKEN,
    INSTAGRAM_APP_SECRET,
    JWT_SECRET,
    CLOUDINARY_CLOUD_NAME,
    CLOUDINARY_API_KEY,
    CLOUDINARY_API_SECRET
)
from shared.kafka_producer import KafkaProducerPool
from shared.redis_pool import RedisPool
import importlib
_chat_service = importlib.import_module("services.chatai-service.chat_service")
route_inbound_message = _chat_service.route_inbound_message

# Configure Cloudinary
cloudinary.config(
    cloud_name=CLOUDINARY_CLOUD_NAME,
    api_key=CLOUDINARY_API_KEY,
    api_secret=CLOUDINARY_API_SECRET,
    secure=True
)

logger = logging.getLogger("api_gateway.instagram_webhook")
router = APIRouter(prefix="/webhooks", tags=["Webhooks"])


async def get_db():
    async with SessionLocal() as session:
        yield session


# ---------------------------------------------------------------------------
# O(1) Connector lookup with Redis caching
# ---------------------------------------------------------------------------

async def _load_connector_by_id(db: AsyncSession, recipient_id: str) -> PlatformConnector | None:
    """Load active Instagram connector by platform_account_id from DB or Redis cache."""
    try:
        redis_client = RedisPool.get_client()
        cache_key = f"connector:ig:{recipient_id}"
        cached_data = await redis_client.get(cache_key)
        if cached_data:
            cached = json.loads(cached_data)
            # Reconstruct dummy PlatformConnector to avoid breaking downstream signature logic
            c = PlatformConnector(
                business_id=cached["business_id"],
                platform_account_id=recipient_id,
                platform_account_name=cached["platform_account_name"],
                tokens=cached["tokens"],
                status="active"
            )
            return c
    except Exception as e:
        logger.error(f"[Webhook] Redis cache read failed: {e}")

    stmt = select(PlatformConnector).where(
        PlatformConnector.platform == "instagram",
        PlatformConnector.platform_account_id == recipient_id,
        PlatformConnector.status == "active"
    )
    result = await db.execute(stmt)
    c = result.scalar_one_or_none()

    if c:
        try:
            redis_client = RedisPool.get_client()
            cache_key = f"connector:ig:{recipient_id}"
            await redis_client.setex(
                cache_key,
                3600,
                json.dumps({
                    "business_id": str(c.business_id),
                    "platform_account_name": c.platform_account_name,
                    "tokens": c.tokens
                })
            )
        except Exception as e:
            logger.error(f"[Webhook] Redis cache write failed: {e}")
            
    return c


# ---------------------------------------------------------------------------
# Event handlers
# ---------------------------------------------------------------------------

async def process_instagram_media(messaging_event: dict, org_id: str) -> str | None:
    """
    Checks if the Instagram message contains an image or video attachment.
    If it does, download the file and upload it to Cloudinary.
    Returns the Cloudinary secure URL or None.
    """
    message = messaging_event.get("message", {})
    attachments = message.get("attachments", [])
    if not attachments or not isinstance(attachments, list):
        return None
        
    media_url = None
    for att in attachments:
        att_type = att.get("type")
        if att_type in ("image", "video"):
            media_url = att.get("payload", {}).get("url")
            if media_url:
                break
                
    if not media_url:
        return None
        
    try:
        async with httpx.AsyncClient() as client:
            file_resp = await client.get(media_url, timeout=30.0)
            if file_resp.status_code != 200:
                logger.error(f"Failed to download media from Instagram attachment. Status: {file_resp.status_code}")
                return None
                
            file_bytes = file_resp.content
            
            import hashlib
            file_hash = hashlib.sha256(file_bytes).hexdigest()
            folder_path = f"sahayak/org_{org_id}"
            
            result = await asyncio.to_thread(
                cloudinary.uploader.upload,
                file_bytes,
                folder=folder_path,
                public_id=file_hash,
                resource_type="auto"
            )
            return result.get("secure_url")
            
    except Exception as e:
        logger.error(f"Error processing Instagram media: {str(e)}", exc_info=True)
        return None


async def _handle_dm(connector: PlatformConnector, messaging_event: dict, raw_payload: dict, bot_token: str, db: AsyncSession) -> None:
    """Process a single DM messaging event and dispatch to Kafka."""
    sender_id = messaging_event.get("sender", {}).get("id")
    message = messaging_event.get("message", {})
    text = message.get("text", "")
    mid = message.get("mid", "")

    # Skip echo, read receipts, and delivery confirmations
    if message.get("is_echo"):
        return
    if "read" in messaging_event or "delivery" in messaging_event:
        return
        
    # Check if there are attachments/media
    attachments = message.get("attachments", [])
    has_media = False
    if attachments and isinstance(attachments, list):
        for attachment in attachments:
            if attachment.get("type") in ("image", "video"):
                has_media = True
                break

    if not sender_id:
        return
    if not text and not has_media:
        return

    # If the sender is a registered business page in our system, check if we are the customer
    # of that business page (we ignore the message if so to prevent loop and double-saving)
    sender_connector = await _load_connector_by_id(db, sender_id)
    if sender_connector:
        from shared.database.mongodb import MongoDBManager
        mongo_db = MongoDBManager.get_db()
        recipient_id = connector.platform_account_id
        recipient_id_int = int(recipient_id) if str(recipient_id).isdigit() else None
        sender_id_query = {"$in": [recipient_id, recipient_id_int]} if recipient_id_int is not None else recipient_id
        
        existing_conv = await mongo_db.conversations.find_one({
            "platform": "instagram",
            "organization_id": str(sender_connector.business_id),
            "user.sender_id": sender_id_query
        })
        if existing_conv:
            logger.info(f"[Webhook] Ignoring message from business page {sender_id} to page {connector.platform_account_id} as the sender is the seller in this thread.")
            return

    # Process media if present
    media_url = None
    if has_media:
        media_url = await process_instagram_media(messaging_event, str(connector.business_id))

    # [Webhook] DM from {sender_id}: {text!r} (media: {media_url})

    await route_inbound_message(
        org_id=str(connector.business_id),
        bot_name=connector.platform_account_name or "Instagram",
        bot_token=bot_token,
        platform="instagram",
        payload=raw_payload,
        event_type="dm",
        sender_id=sender_id,
        mid=mid,
        message_text=text,
        image_url=media_url
    )


async def _handle_change(connector: PlatformConnector, change: dict, raw_payload: dict, bot_token: str) -> None:
    """Process a single change event (comments, mentions) and dispatch to Kafka."""
    field = change.get("field")
    value = change.get("value", {})

    # [Webhook] Change event: field={field}

    await route_inbound_message(
        org_id=str(connector.business_id),
        bot_name=connector.platform_account_name or "Instagram",
        bot_token=bot_token,
        platform="instagram",
        payload=raw_payload,
        event_type=field,
        from_user=value.get("from", {}),
        comment_id=value.get("id")
    )


# ---------------------------------------------------------------------------
# Route
# ---------------------------------------------------------------------------

@router.api_route("/instagram", methods=["GET", "POST"])
async def instagram_webhook(request: Request, db: AsyncSession = Depends(get_db)):

    # --- GET: Meta webhook verification challenge ---
    if request.method == "GET":
        params = request.query_params
        mode = params.get("hub.mode")
        challenge = params.get("hub.challenge")
        token = params.get("hub.verify_token")

        if not challenge:
            return HTMLResponse(content="<p>Webhook is live.</p>", status_code=200)
        if mode != "subscribe":
            return HTMLResponse(content="<p>Invalid hub.mode.</p>", status_code=400)
        if token != INSTAGRAM_VERIFY_TOKEN:
            logger.warning(f"[Webhook] Verify token mismatch: {token!r}")
            return HTMLResponse(content="<p>Verification token mismatch.</p>", status_code=403)

        return PlainTextResponse(content=challenge, status_code=200)

    # --- POST: Incoming event from Meta ---
    raw_body = await request.body()
    # 1. Validate signature early
    signature = request.headers.get("X-Hub-Signature-256")
    if signature:
        expected = hmac.new(
            INSTAGRAM_APP_SECRET.encode("utf-8"),
            raw_body,
            hashlib.sha256
        ).hexdigest()
        received = signature.replace("sha256=", "")
        if not hmac.compare_digest(expected, received):
            logger.warning("[Webhook] Signature validation failed.")
            return Response(content="Unauthorized", status_code=403)
    else:
        logger.warning("[Webhook] Missing X-Hub-Signature-256 header.")

    try:
        payload = json.loads(raw_body)
    except json.JSONDecodeError:
        return Response(status_code=400)

    # Only process Instagram events
    if payload.get("object") != "instagram":
        return Response(status_code=200)

    # 2. Process entries
    for entry in payload.get("entry", []):
        entry_id = str(entry.get("id", ""))
        
        # --- DM events ---
        for messaging_event in entry.get("messaging", []):
            # O(1) query / caching lookup using entry_id (always the business account IG_ID)
            connector = await _load_connector_by_id(db, entry_id)
            if not connector:
                logger.warning(f"[Webhook] Entry {entry_id} not found in connectors. Dumping DM.")
                continue

            # Decrypt access token if encrypted
            bot_token = connector.tokens.get("access_token")
            if connector.tokens.get("access_token_encrypted"):
                from shared.utils import decrypt_access_token
                try:
                    bot_token = decrypt_access_token(
                        connector.tokens["token_iv"],
                        connector.tokens["token_ciphertext"],
                        connector.tokens["token_auth_tag"],
                        str(JWT_SECRET)
                    )
                except Exception as e:
                    logger.error(f"Failed to decrypt Instagram access token: {e}")
                    continue

            # Intercept read receipts
            if "read" in messaging_event:
                sender_id = messaging_event.get("sender", {}).get("id")
                watermark = messaging_event.get("read", {}).get("watermark")
                if sender_id and watermark:
                    try:
                        await route_inbound_message(
                            org_id=str(connector.business_id),
                            bot_name=connector.platform_account_name or "Instagram",
                            bot_token=bot_token,
                            platform="instagram",
                            payload=payload,
                            event_type="seen",
                            sender_id=sender_id,
                            watermark=watermark
                        )
                    except Exception as e:
                        logger.error(f"[Webhook] Error sending seen event to Kafka: {e}")
                continue

            # Check message deduplication/idempotency via Redis
            mid = messaging_event.get("message", {}).get("mid")
            if mid:
                try:
                    redis_client = RedisPool.get_client()
                    is_new = await redis_client.set(f"webhook:processed:{mid}", "1", ex=86400, nx=True)
                    if not is_new:
                        continue
                except Exception as e:
                    logger.error(f"[Webhook] Redis deduplication error: {e}")

            try:
                await _handle_dm(connector, messaging_event, payload, bot_token, db)
            except Exception as e:
                logger.error(f"[Webhook] Error processing DM: {e}", exc_info=True)

        # --- Change events (comments, mentions) ---
        for change in entry.get("changes", []):
            connector = await _load_connector_by_id(db, entry_id)
            if not connector:
                logger.warning(f"[Webhook] Change entry {entry_id} not found in connectors. Dumping.")
                continue

            # Decrypt access token if encrypted
            bot_token = connector.tokens.get("access_token")
            if connector.tokens.get("access_token_encrypted"):
                from shared.utils import decrypt_access_token
                try:
                    bot_token = decrypt_access_token(
                        connector.tokens["token_iv"],
                        connector.tokens["token_ciphertext"],
                        connector.tokens["token_auth_tag"],
                        str(JWT_SECRET)
                    )
                except Exception as e:
                    logger.error(f"Failed to decrypt Instagram access token: {e}")
                    continue

            try:
                await _handle_change(connector, change, payload, bot_token)
            except Exception as e:
                logger.error(f"[Webhook] Error processing change event: {e}", exc_info=True)

    # Always return 200 — Meta retries on non-200
    return Response(status_code=200)