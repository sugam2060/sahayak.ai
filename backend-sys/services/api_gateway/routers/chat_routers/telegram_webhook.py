from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from shared.database.engine import SessionLocal
from shared.database.schema.platform_connectors import PlatformConnector
import logging

logger = logging.getLogger("api_gateway.telegram_webhook")
router = APIRouter(prefix="/webhooks", tags=["Webhooks"])

async def get_db():
    async with SessionLocal() as session:
        yield session

@router.post("/telegram/{bot_token}")
async def telegram_webhook(
    bot_token: str,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """
    Webhook endpoint to receive updates/messages from Telegram Bot.
    """
    try:
        payload = await request.json()
        print(f"[Telegram Webhook] Received payload for token: {bot_token[:10]}...", flush=True)
        
        # Look up the connector associated with this bot token
        stmt = select(PlatformConnector).where(
            PlatformConnector.platform == "telegram"
        )
        result = await db.execute(stmt)
        connectors = result.scalars().all()
        
        # Find matching connector in python to support all DB dialects and avoid complex JSONB query issues
        connector = None
        for c in connectors:
            if c.tokens.get("bot_token") == bot_token:
                connector = c
                break
                
        if connector:
            org_id = connector.business_id
            bot_name = connector.platform_account_name or "UnknownBot"
            print(f"[Telegram Message] Bot: @{bot_name} | Org ID: {org_id}", flush=True)
            
            message = payload.get("message", {})
            if message:
                sender = message.get("from", {})
                chat = message.get("chat", {})
                text = message.get("text", "")
                sender_name = sender.get("username") or sender.get("first_name") or "Unknown"
                print(f"   From: {sender_name} (ID: {sender.get('id')})", flush=True)
                print(f"   Chat ID: {chat.get('id')} | Text: {text}", flush=True)
            else:
                print(f"   Payload (non-message update): {payload}", flush=True)
        else:
            print(f"[Telegram Webhook] WARNING: Received update but no matching connector found for token: {bot_token[:10]}...", flush=True)
            
        return {"status": "ok"}
    except Exception as e:
        print(f"[Telegram Webhook] Error processing webhook: {str(e)}", flush=True)
        logger.error("Error processing Telegram webhook: %s", str(e), exc_info=True)
        return {"status": "error", "message": str(e)}
