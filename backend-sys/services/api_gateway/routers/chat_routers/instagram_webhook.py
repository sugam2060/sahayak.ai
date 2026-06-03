import logging
import json
from fastapi import APIRouter, Request, Depends, Response
from fastapi.responses import HTMLResponse, PlainTextResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from shared.database.engine import SessionLocal
from shared.database.schema.platform_connectors import PlatformConnector
from shared.config import INSTAGRAM_VERIFY_TOKEN
from shared.kafka_producer import KafkaProducerPool

logger = logging.getLogger("api_gateway.instagram_webhook")
router = APIRouter(prefix="/webhooks", tags=["Webhooks"])


async def get_db():
    async with SessionLocal() as session:
        yield session


# ---------------------------------------------------------------------------
# Connector lookup
# ---------------------------------------------------------------------------

async def _load_connectors(db: AsyncSession) -> list[PlatformConnector]:
    """Load all active Instagram connectors from DB."""
    stmt = select(PlatformConnector).where(
        PlatformConnector.platform == "instagram",
        PlatformConnector.status == "active"
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


def _find_connector(
    connectors: list[PlatformConnector],
    recipient_id: str
) -> PlatformConnector | None:
    """Find a connector whose platform_account_id matches the recipient_id."""
    for c in connectors:
        if str(c.platform_account_id) == recipient_id:
            return c
    return None


# ---------------------------------------------------------------------------
# Event handlers
# ---------------------------------------------------------------------------

async def _handle_dm(connector: PlatformConnector, messaging_event: dict, raw_payload: dict) -> None:
    """Process a single DM messaging event and dispatch to Kafka."""
    sender_id = messaging_event.get("sender", {}).get("id")
    message = messaging_event.get("message", {})
    text = message.get("text", "")
    mid = message.get("mid", "")

    # Skip echo (bot's own messages), read receipts, and delivery confirmations
    if message.get("is_echo"):
        return
    if "read" in messaging_event or "delivery" in messaging_event:
        return
    if not sender_id or not text:
        return

    logger.info(f"[Webhook] DM from {sender_id}: {text!r}")

    await KafkaProducerPool.send_message("chat_service", {
        "org_id": str(connector.business_id),
        "bot_name": connector.platform_account_name or "Instagram",
        "bot_token": connector.tokens.get("access_token", ""),
        "platform": "instagram",
        "event_type": "dm",
        "direction": "inbound",
        "sender_id": sender_id,
        "mid": mid,
        "message_text": text,
        "payload": raw_payload,
    })


async def _handle_change(connector: PlatformConnector, change: dict, raw_payload: dict) -> None:
    """Process a single change event (comments, mentions) and dispatch to Kafka."""
    field = change.get("field")
    value = change.get("value", {})

    logger.info(f"[Webhook] Change event: field={field}")

    await KafkaProducerPool.send_message("chat_service", {
        "org_id": str(connector.business_id),
        "bot_name": connector.platform_account_name or "Instagram",
        "bot_token": connector.tokens.get("access_token", ""),
        "platform": "instagram",
        "event_type": field,
        "direction": "inbound",
        "from_user": value.get("from", {}),
        "comment_id": value.get("id"),
        "payload": raw_payload,
    })


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

        logger.info("[Webhook] Verification challenge accepted.")
        return PlainTextResponse(content=challenge, status_code=200)

    # --- POST: Incoming event from Meta ---
    raw_body = await request.body()

    try:
        payload = json.loads(raw_body)
    except json.JSONDecodeError:
        return Response(status_code=400)

    # Only process Instagram events
    if payload.get("object") != "instagram":
        return Response(status_code=200)

    # Load all Instagram connectors once
    try:
        connectors = await _load_connectors(db)
    except Exception as e:
        logger.error(f"[Webhook] DB error: {e}", exc_info=True)
        return Response(status_code=200)

    if not connectors:
        logger.warning("[Webhook] No active Instagram connectors in DB. Dumping event.")
        return Response(status_code=200)

    # Process each entry
    for entry in payload.get("entry", []):

        # --- DM events ---
        for messaging_event in entry.get("messaging", []):
            recipient_id = str(messaging_event.get("recipient", {}).get("id", ""))
            connector = _find_connector(connectors, recipient_id)

            if not connector:
                logger.info(f"[Webhook] Recipient {recipient_id} not found in connectors. Dumping DM.")
                continue

            try:
                await _handle_dm(connector, messaging_event, payload)
            except Exception as e:
                logger.error(f"[Webhook] Error processing DM: {e}", exc_info=True)

        # --- Change events (comments, mentions) ---
        for change in entry.get("changes", []):
            # For change events, use entry.id as the account identifier
            entry_id = str(entry.get("id", ""))
            connector = _find_connector(connectors, entry_id)

            if not connector:
                # Fallback: use first available connector for change events
                connector = connectors[0]

            try:
                await _handle_change(connector, change, payload)
            except Exception as e:
                logger.error(f"[Webhook] Error processing change event: {e}", exc_info=True)

    # Always return 200 — Meta retries on non-200
    return Response(status_code=200)