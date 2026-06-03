import hmac
import hashlib
import logging
import json
from fastapi import APIRouter, Request, Depends, Response
from fastapi.responses import HTMLResponse, PlainTextResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from shared.database.engine import SessionLocal
from shared.database.schema.platform_connectors import PlatformConnector
from shared.config import INSTAGRAM_VERIFY_TOKEN, INSTAGRAM_APP_SECRET
from shared.kafka_producer import KafkaProducerPool

logger = logging.getLogger("api_gateway.instagram_webhook")
router = APIRouter(prefix="/webhooks", tags=["Webhooks"])


async def get_db():
    async with SessionLocal() as session:
        yield session


# ---------------------------------------------------------------------------
# Signature validation
# ---------------------------------------------------------------------------

def _verify_signature(raw_body: bytes, signature_header: str) -> bool:
    """
    Validates Meta's X-Hub-Signature-256 header.
    Computed as HMAC-SHA256 of the raw request body using INSTAGRAM_APP_SECRET.
    Returns False (not raises) so the caller can log and return 403 cleanly.
    """
    if not signature_header or not signature_header.startswith("sha256="):
        logger.warning("[InstagramWebhook] Missing or malformed X-Hub-Signature-256 header.")
        return False

    expected = signature_header[len("sha256="):]

    computed = hmac.HMAC(
        key=INSTAGRAM_APP_SECRET.encode("utf-8"),
        msg=raw_body,
        digestmod=hashlib.sha256
    ).hexdigest()

    valid = hmac.compare_digest(computed, expected)
    if not valid:
        logger.warning(
            "[InstagramWebhook] Signature mismatch. "
            f"expected={expected[:16]}... computed={computed[:16]}..."
        )
    return valid


# ---------------------------------------------------------------------------
# Connector lookup (cached per request — avoids N queries per entry)
# ---------------------------------------------------------------------------

async def _get_connector_map(db: AsyncSession) -> dict[str, PlatformConnector]:
    """Returns a dict of { platform_account_id -> PlatformConnector } for all Instagram connectors."""
    stmt = select(PlatformConnector).where(PlatformConnector.platform == "instagram")
    result = await db.execute(stmt)
    return {str(c.platform_account_id): c for c in result.scalars().all()}


# ---------------------------------------------------------------------------
# Event handlers
# ---------------------------------------------------------------------------

async def _handle_messaging(
    connector: PlatformConnector,
    entry: dict,
    messaging_event: dict,
    raw_payload: dict
) -> None:
    """
    Handles DM events (instagram_business_manage_messages).

    Messaging event shape:
    {
      "sender":    { "id": "<sender-igsid>" },
      "recipient": { "id": "<your-ig-account-id>" },
      "timestamp": 1234567890,
      "message":   { "mid": "...", "text": "Hello!" }
                OR "read":    { "mid": "..." }
                OR "delivery":{ "mids": [...], "watermark": ... }
    }
    """
    sender_id = messaging_event.get("sender", {}).get("id")
    message   = messaging_event.get("message", {})
    message_text = message.get("text", "")
    mid = message.get("mid", "")

    # Ignore echo events (messages sent by the business itself)
    if message.get("is_echo"):
        logger.debug(f"[InstagramWebhook] Skipping echo message mid={mid}")
        return

    # Ignore read receipts and delivery confirmations — not actionable
    if "read" in messaging_event or "delivery" in messaging_event:
        logger.debug(f"[InstagramWebhook] Skipping read/delivery event for account={entry.get('id')}")
        return

    logger.info(
        f"[InstagramWebhook] DM event | "
        f"account={entry.get('id')} sender={sender_id} mid={mid} text={message_text!r}"
    )

    kafka_event = {
        "org_id": str(connector.business_id),
        "bot_name": connector.platform_account_name or "InstagramBusiness",
        "bot_token": connector.tokens.get("access_token", ""),
        "platform": "instagram",
        "event_type": "dm",
        "direction": "inbound",
        "sender_id": sender_id,
        "mid": mid,
        "message_text": message_text,
        "payload": raw_payload,
    }
    await KafkaProducerPool.send_message("chat_service", kafka_event)
    logger.info(f"[InstagramWebhook] DM event dispatched to Kafka | sender={sender_id} text={message_text!r}")


async def _handle_change(
    connector: PlatformConnector,
    entry: dict,
    change: dict,
    raw_payload: dict
) -> None:
    """
    Handles comment / mention / story_mention change events (instagram_business_manage_comments).

    Change shape:
    {
      "field": "comments",
      "value": {
        "id": "<comment-id>",
        "text": "Great post!",
        "from": { "id": "...", "username": "..." },
        "media": { "id": "...", "media_product_type": "POST" }
      }
    }
    """
    field = change.get("field")
    value = change.get("value", {})
    comment_id = value.get("id")
    comment_text = value.get("text", "")
    from_user = value.get("from", {})

    logger.info(
        f"[InstagramWebhook] Change event | "
        f"account={entry.get('id')} field={field} comment_id={comment_id} "
        f"from={from_user.get('username')} text={comment_text!r}"
    )

    kafka_event = {
        "org_id": str(connector.business_id),
        "bot_name": connector.platform_account_name or "InstagramBusiness",
        "bot_token": connector.tokens.get("access_token", ""),
        "platform": "instagram",
        "event_type": field,          # "comments", "mentions", "story_mentions", etc.
        "direction": "inbound",
        "from_user": from_user,
        "comment_id": comment_id,
        "payload": raw_payload,
    }
    await KafkaProducerPool.send_message("chat_service", kafka_event)
    logger.info(f"[InstagramWebhook] Change event dispatched to Kafka | field={field} comment_id={comment_id}")


# ---------------------------------------------------------------------------
# Route
# ---------------------------------------------------------------------------

@router.api_route("/instagram", methods=["GET", "POST"])
async def instagram_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    # -----------------------------------------------------------------------
    # GET — Meta webhook verification challenge
    # -----------------------------------------------------------------------
    if request.method == "GET":
        params          = request.query_params
        hub_mode        = params.get("hub.mode")
        hub_challenge   = params.get("hub.challenge")
        hub_verify_token = params.get("hub.verify_token")

        if not hub_challenge:
            return HTMLResponse(content="<p>Webhook is live.</p>", status_code=200)

        if hub_mode != "subscribe":
            logger.warning(f"[InstagramWebhook] Unexpected hub.mode: {hub_mode}")
            return HTMLResponse(content="<p>Invalid hub.mode.</p>", status_code=400)

        if hub_verify_token != INSTAGRAM_VERIFY_TOKEN:
            logger.warning(
                f"[InstagramWebhook] Verify token mismatch. received={hub_verify_token!r}"
            )
            return HTMLResponse(content="<p>Verification token mismatch.</p>", status_code=403)

        logger.info("[InstagramWebhook] Webhook verified successfully.")
        return PlainTextResponse(content=hub_challenge, status_code=200)

    # -----------------------------------------------------------------------
    # POST — Incoming event payload
    # -----------------------------------------------------------------------
    # 1. Read raw body first — required for HMAC validation
    raw_body = await request.body()
    
    # Debug log the incoming request
    headers_dict = dict(request.headers)
    logger.info(f"[InstagramWebhook] Incoming request headers: {json.dumps(headers_dict)}")
    try:
        body_str = raw_body.decode("utf-8")
        logger.info(f"[InstagramWebhook] Raw request body: {body_str}")
    except Exception as e:
        logger.info(f"[InstagramWebhook] Raw request body (bytes): {raw_body}")

    # 2. Validate X-Hub-Signature-256 — reject anything that doesn't come from Meta
    signature = request.headers.get("X-Hub-Signature-256", "")
    if not _verify_signature(raw_body, signature):
        logger.warning("[InstagramWebhook] Rejected POST — invalid signature.")
        return Response(status_code=403)

    # 3. Parse JSON
    try:
        payload = json.loads(raw_body)
    except json.JSONDecodeError as e:
        logger.error(f"[InstagramWebhook] Failed to parse JSON payload: {e}")
        return Response(status_code=400)

    logger.debug(f"[InstagramWebhook] Payload received:\n{json.dumps(payload, indent=2)}")

    # 4. Validate object type
    if payload.get("object") != "instagram":
        logger.warning(f"[InstagramWebhook] Unexpected object type: {payload.get('object')}")
        return Response(status_code=200)  # Return 200 anyway — Meta will retry on non-200

    # 5. Load all Instagram connectors in one query
    try:
        connector_map = await _get_connector_map(db)
    except Exception as e:
        logger.error(f"[InstagramWebhook] DB error loading connectors: {e}", exc_info=True)
        return Response(status_code=200)  # Don't return 5xx — Meta would retry indefinitely

    # 6. Route each entry to the correct connector
    entries = payload.get("entry", [])
    logger.info(f"[InstagramWebhook] Processing {len(entries)} entries.")

    for entry in entries:
        account_id = str(entry.get("id", ""))
        connector  = connector_map.get(account_id)

        if not connector:
            logger.warning(f"[InstagramWebhook] No connector found for account_id={account_id} — skipping entry.")
            continue

        # DM events
        for messaging_event in entry.get("messaging", []):
            try:
                await _handle_messaging(connector, entry, messaging_event, payload)
            except Exception as e:
                logger.error(
                    f"[InstagramWebhook] Error handling messaging event for account={account_id}: {e}",
                    exc_info=True
                )

        # Comment / mention events
        for change in entry.get("changes", []):
            try:
                await _handle_change(connector, entry, change, payload)
            except Exception as e:
                logger.error(
                    f"[InstagramWebhook] Error handling change event for account={account_id}: {e}",
                    exc_info=True
                )

    # Meta requires 200 within 20s — always return it even on partial failures
    return Response(status_code=200)