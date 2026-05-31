import logging
import json
from fastapi import APIRouter, Depends, Request, Query, HTTPException
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

@router.api_route("/instagram", methods=["GET", "POST"])
async def instagram_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """
    Instagram Webhook Endpoint aligned with the requested design.
    """
    if request.method == "POST":
        try:
            payload = await request.json()
            # Print the payload as pretty-printed JSON as requested
            print(json.dumps(payload, indent=4))

            # Database / Routing logic
            entries = payload.get("entry", [])
            if entries:
                stmt = select(PlatformConnector).where(PlatformConnector.platform == "instagram")
                result = await db.execute(stmt)
                connectors = result.scalars().all()

                for entry in entries:
                    instagram_account_id = entry.get("id")
                    if not instagram_account_id:
                        continue

                    # Match connector
                    connector = None
                    for c in connectors:
                        if str(c.platform_account_id) == str(instagram_account_id):
                            connector = c
                            break

                    if connector:
                        org_id = connector.business_id
                        platform_account_name = connector.platform_account_name or "InstagramBusiness"
                        access_token = connector.tokens.get("access_token", "dummy_token")

                        # Forward to Kafka
                        message_event = {
                            "org_id": str(org_id),
                            "bot_name": platform_account_name,
                            "bot_token": access_token,
                            "platform": "instagram",
                            "direction": "inbound",
                            "payload": payload
                        }
                        await KafkaProducerPool.send_message("chat_service", message_event)
                        logger.info("Successfully produced Instagram message event to Kafka.")

            return HTMLResponse(content="<p>This is POST Request, Hello Webhook !</p>", status_code=200)

        except Exception as e:
            logger.error("Error processing Instagram webhook POST: %s", str(e), exc_info=True)
            return HTMLResponse(content=f"<p>Error: {str(e)}</p>", status_code=500)

    elif request.method == "GET":
        # Extract query parameters
        params = request.query_params
        hub_mode = params.get("hub.mode")
        hub_challenge = params.get("hub.challenge")
        hub_verify_token = params.get("hub.verify_token")

        if hub_challenge:
            # Optionally check verify token matches config
            if hub_verify_token == INSTAGRAM_VERIFY_TOKEN:
                logger.info("Instagram Webhook verified successfully!")
                return PlainTextResponse(content=hub_challenge, status_code=200)
            else:
                logger.warning("Instagram Webhook verification failed due to invalid token: %s", hub_verify_token)
                return HTMLResponse(content="<p>Verification token mismatch</p>", status_code=403)
        else:
            return HTMLResponse(content="<p>This is GET Request</p>", status_code=200)
