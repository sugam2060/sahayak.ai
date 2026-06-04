from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from shared.database.engine import SessionLocal
from shared.database.schema.platform_connectors import PlatformConnector
import importlib
_chat_service = importlib.import_module("services.chatai-service.chat_service")
route_inbound_message = _chat_service.route_inbound_message
import logging

import logging
import httpx
import asyncio
import cloudinary
import cloudinary.uploader
from shared.config import CLOUDINARY_CLOUD_NAME, CLOUDINARY_API_KEY, CLOUDINARY_API_SECRET

# Configure Cloudinary
cloudinary.config(
    cloud_name=CLOUDINARY_CLOUD_NAME,
    api_key=CLOUDINARY_API_KEY,
    api_secret=CLOUDINARY_API_SECRET,
    secure=True
)

logger = logging.getLogger("api_gateway.telegram_webhook")
router = APIRouter(prefix="/webhooks", tags=["Webhooks"])

async def get_db():
    async with SessionLocal() as session:
        yield session

async def process_telegram_media(bot_token: str, message: dict, org_id: str) -> str | None:
    """
    Checks if the Telegram message contains a photo, video, or document (image/video).
    If it does, download the file from Telegram and upload it to Cloudinary.
    Returns the Cloudinary secure URL or None.
    """
    file_id = None
    
    # 1. Check for Photo (array of PhotoSize, take the last/largest one)
    if "photo" in message and isinstance(message["photo"], list) and len(message["photo"]) > 0:
        file_id = message["photo"][-1].get("file_id")
    
    # 2. Check for Video
    elif "video" in message and isinstance(message["video"], dict):
        file_id = message["video"].get("file_id")
        
    # 3. Check for Document if it is image/video
    elif "document" in message and isinstance(message["document"], dict):
        doc = message["document"]
        mime_type = doc.get("mime_type", "")
        if mime_type.startswith("image/") or mime_type.startswith("video/"):
            file_id = doc.get("file_id")
            
    if not file_id:
        return None
        
    try:
        async with httpx.AsyncClient() as client:
            # Get file path from Telegram
            get_file_url = f"https://api.telegram.org/bot{bot_token}/getFile"
            resp = await client.get(get_file_url, params={"file_id": file_id}, timeout=10.0)
            if resp.status_code != 200:
                logger.error(f"Failed to get file info from Telegram. Status: {resp.status_code}, Body: {resp.text}")
                return None
                
            file_info = resp.json()
            if not file_info.get("ok"):
                logger.error(f"Telegram getFile returned ok=False: {file_info}")
                return None
                
            file_path = file_info["result"].get("file_path")
            if not file_path:
                logger.error("No file_path returned in Telegram getFile response")
                return None
                
            # Download file bytes
            download_url = f"https://api.telegram.org/file/bot{bot_token}/{file_path}"
            file_resp = await client.get(download_url, timeout=30.0)
            if file_resp.status_code != 200:
                logger.error(f"Failed to download file from Telegram. Status: {file_resp.status_code}")
                return None
                
            file_bytes = file_resp.content
            
            # Upload file bytes to Cloudinary
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
        logger.error(f"Error processing Telegram media: {str(e)}", exc_info=True)
        return None

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
            
            # If payload has a message, process media attachments
            message = payload.get("message")
            if message and isinstance(message, dict):
                media_url = await process_telegram_media(bot_token, message, str(org_id))
                if media_url:
                    payload["message"]["image_url"] = media_url
            
            # Route webhook payload via Kafka topic 'chat_service'
            await route_inbound_message(
                org_id=str(org_id),
                bot_name=bot_name,
                bot_token=bot_token,
                platform="telegram",
                payload=payload
            )
        else:
            logger.warning(f"[Telegram Webhook] WARNING: Received update but no matching connector found for token: {bot_token[:10]}...")
            
        return {"status": "ok"}
    except Exception as e:
        logger.error("Error processing Telegram webhook: %s", str(e), exc_info=True)
        return {"status": "error", "message": str(e)}
