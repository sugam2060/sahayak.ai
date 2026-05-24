from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from shared.database.engine import SessionLocal
from shared.database.schema.platform_connectors import PlatformConnector
from services.workers.chat_service import route_telegram_message
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
            
            # Route webhook payload via Kafka topic 'chat_service'
            await route_telegram_message(
                org_id=str(org_id),
                bot_name=bot_name,
                bot_token=bot_token,
                payload=payload
            )
        else:
            logger.warning(f"[Telegram Webhook] WARNING: Received update but no matching connector found for token: {bot_token[:10]}...")
            
        return {"status": "ok"}
    except Exception as e:
        logger.error("Error processing Telegram webhook: %s", str(e), exc_info=True)
        return {"status": "error", "message": str(e)}
