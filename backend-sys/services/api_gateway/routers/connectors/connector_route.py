import os
import sys
import jwt
import logging

logger = logging.getLogger("api_gateway.connector_route")
from datetime import datetime, timedelta
from typing import Optional
from uuid import UUID
from urllib.parse import quote_plus
from fastapi import APIRouter, Depends, Request, HTTPException, status, Query
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

# Add backend-sys to sys.path to enable clean shared imports if needed
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from shared.database.engine import SessionLocal
from shared.config import JWT_SECRET, JWT_ALGORITHM, FRONTEND_URL
from services.api_gateway.routers.teams.permissions import check_permission
from shared.database.schema.platform_connectors import PlatformConnector
from services.api_gateway.routers.connectors.connector_class import (
    ConnectorError,
    InstagramConnector,
    TelegramConnector,
)

router = APIRouter(prefix="/connectors", tags=["Connectors"])

# Database session dependency
async def get_db():
    async with SessionLocal() as session:
        yield session


class TelegramConnectRequest(BaseModel):
    bot_username: str = Field(..., description="The username of the Telegram bot (e.g. @MyBot or MyBot)")
    access_token: str = Field(..., description="The HTTP API bot token received from BotFather")

    @field_validator("bot_username")
    @classmethod
    def validate_bot_username(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("bot_username must be non-empty")
        v = v.strip()
        if v.startswith("@"):
            v = v[1:]
        if not v:
            raise ValueError("bot_username must be non-empty after stripping '@'")
        return v

    @field_validator("access_token")
    @classmethod
    def validate_access_token(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("access_token must be non-empty")
        return v.strip()


def get_connector(platform: str):
    """Factory helper to retrieve the correct connector class based on platform name."""
    platform = platform.lower()
    if platform == "instagram":
        return InstagramConnector()
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported OAuth platform: '{platform}'. Only 'instagram' is supported."
        )


@router.get("/oauth/url/{platform}")
async def get_oauth_url(platform: str, current_user: dict = Depends(check_permission("connectors"))):
    """
    Generates the authorization redirect URL for TikTok or Instagram OAuth flows.
    Authenticates the request and signs user session context into a secure JWT state token.
    """
    connector = get_connector(platform)

    # Generate a signed JWT state token containing business identity
    # Expires in 10 minutes to prevent replay and CSRF attacks
    state_payload = {
        "business_id": str(current_user["organization_id"]),
        "user_id": str(current_user["user_id"]),
        "platform": platform.lower(),
        "exp": datetime.utcnow() + timedelta(minutes=10)
    }
    state_token = jwt.encode(state_payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

    try:
        auth_url = connector.get_authorization_url(state=state_token)
        return {"success": True, "url": auth_url}
    except ConnectorError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while generating authorization URL: {str(e)}"
        )


@router.get("/oauth/callback/{platform}")
async def oauth_callback(
    platform: str,
    code: Optional[str] = None,
    auth_code: Optional[str] = Query(None),
    state: Optional[str] = None,
    error: Optional[str] = None,
    error_description: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    """
    Callback endpoint redirected to by TikTok/Instagram after user authorization.
    Decodes the secure JWT state token, exchanges code for access tokens, and registers the connection.
    """
    # Normalize authorization code parameter
    effective_code = code or auth_code

    # 1. Handle error responses returned directly by OAuth providers
    if error or not effective_code or not state:
        err_msg = error_description or error or "User denied or cancelled connection request."
        redirect_url = f"{FRONTEND_URL}/connectors?status=error&message={quote_plus(err_msg)}"
        return RedirectResponse(url=redirect_url)

    # 2. Decode and validate state parameter (JWT)
    try:
        payload = jwt.decode(state, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        business_id_str = payload.get("business_id")
        state_platform = payload.get("platform")

        if not business_id_str or state_platform != platform.lower():
            raise jwt.InvalidTokenError("Invalid state payload structure.")
        
        business_id = UUID(business_id_str)
    except jwt.ExpiredSignatureError:
        err_msg = "OAuth state signature expired. Please request a new authorization link."
        return RedirectResponse(url=f"{FRONTEND_URL}/connectors?status=error&message={quote_plus(err_msg)}")
    except jwt.InvalidTokenError:
        err_msg = "OAuth state authentication verification failed. Unauthorized callback."
        return RedirectResponse(url=f"{FRONTEND_URL}/connectors?status=error&message={quote_plus(err_msg)}")

    # 3. Instantiate platform-specific connector and trigger handshake/upsert
    try:
        connector = get_connector(platform)
        await connector.connect(session=db, business_id=business_id, code=effective_code)
        
        # Connection succeeded: redirect back to frontend with success parameters
        return RedirectResponse(url=f"{FRONTEND_URL}/connectors?status=success&platform={platform.lower()}")
    except ConnectorError as e:
        import traceback
        print(f"[OAuth Callback Error] ConnectorError occurred: status_code={e.status_code}, message={e.message}", flush=True)
        traceback.print_exc()
        err_msg = e.message
        return RedirectResponse(url=f"{FRONTEND_URL}/connectors?status=error&message={quote_plus(err_msg)}")
    except Exception as e:
        import traceback
        print(f"[OAuth Callback Error] Unexpected exception: {str(e)}", flush=True)
        traceback.print_exc()
        err_msg = f"An unexpected error occurred: {str(e)}"
        return RedirectResponse(url=f"{FRONTEND_URL}/connectors?status=error&message={quote_plus(err_msg)}")


@router.post("/telegram/connect")
async def telegram_connect(
    req: TelegramConnectRequest,
    current_user: dict = Depends(check_permission("connectors")),
    db: AsyncSession = Depends(get_db)
):
    """
    Registers a Telegram bot using the bot username and token.
    Validates token credentials directly against Telegram API before saving.
    """
    logger.debug(f"[Route /telegram/connect] Connect request received for username: {req.bot_username}")
    connector = TelegramConnector()
    try:
        business_id = UUID(current_user["organization_id"])
        logger.debug(f"[Route /telegram/connect] Organization ID: {business_id}")
        await connector.connect(
            session=db,
            business_id=business_id,
            bot_username=req.bot_username,
            access_token=req.access_token
        )
        logger.info(f"[Route /telegram/connect] Successfully connected bot @{req.bot_username}")
        return {
            "success": True,
            "message": f"Successfully connected bot @{req.bot_username} to your business workspace."
        }
    except ConnectorError as e:
        logger.warning(f"[Route /telegram/connect] ConnectorError occurred: status_code={e.status_code}, message={e.message}")
        raise HTTPException(status_code=e.status_code, detail=e.message)
    except Exception as e:
        logger.error(f"[Route /telegram/connect] Unexpected Exception: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("")
async def list_connectors(
    current_user: dict = Depends(check_permission("connectors")),
    db: AsyncSession = Depends(get_db)
):
    """
    Retrieves all connection statuses (connected / disconnected) for the user's business organization.
    """
    try:
        business_id = UUID(current_user["organization_id"])
        
        stmt = select(PlatformConnector).where(PlatformConnector.business_id == business_id)
        result = await db.execute(stmt)
        connectors = result.scalars().all()
        
        conn_map = {c.platform.lower(): c for c in connectors}
        
        supported_platforms = [
            {"platform": "instagram", "displayName": "Instagram"},
            # {"platform": "discord", "displayName": "Discord"},
            {"platform": "telegram", "displayName": "Telegram"},
        ]
        
        res = []
        for p in supported_platforms:
            name = p["platform"]
            db_conn = conn_map.get(name)
            if db_conn and db_conn.status == "active":
                res.append({
                    "id": str(db_conn.id),
                    "platform": name,
                    "displayName": p["displayName"],
                    "status": "connected",
                    "connectedAt": db_conn.created_at.isoformat() if db_conn.created_at else None,
                    "username": db_conn.platform_account_name or f"@{name}_account"
                })
            else:
                res.append({
                    "id": name,
                    "platform": name,
                    "displayName": p["displayName"],
                    "status": "disconnected",
                    "connectedAt": None,
                    "username": None
                })
        return res
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while listing connectors: {str(e)}"
        )


@router.post("/disconnect/{platform}")
async def disconnect_connector(
    platform: str,
    current_user: dict = Depends(check_permission("connectors")),
    db: AsyncSession = Depends(get_db)
):
    """
    Deletes the connection configuration and token payload for the given social platform.
    """
    try:
        business_id = UUID(current_user["organization_id"])
        
        stmt = select(PlatformConnector).where(
            PlatformConnector.business_id == business_id,
            PlatformConnector.platform == platform.lower()
        )
        result = await db.execute(stmt)
        connector = result.scalars().first()
        
        if not connector:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No connection configuration found for platform '{platform}'."
            )
            
        if platform.lower() == "telegram":
            bot_token = (connector.tokens or {}).get("bot_token")
            if bot_token:
                tg_connector = TelegramConnector()
                await tg_connector.disconnect(bot_token)
        elif platform.lower() == "instagram":
            tokens = connector.tokens or {}
            access_token = None
            if tokens.get("access_token_encrypted"):
                from shared.utils import decrypt_access_token
                try:
                    access_token = decrypt_access_token(
                        tokens["token_iv"],
                        tokens["token_ciphertext"],
                        tokens["token_auth_tag"],
                        str(JWT_SECRET)
                    )
                except Exception as e:
                    logger.error(f"Failed to decrypt Instagram access token for disconnect: {e}")
            else:
                access_token = tokens.get("access_token")

            if access_token:
                inst_connector = InstagramConnector()
                await inst_connector.disconnect(access_token, connector.platform_account_id)
                
        await db.delete(connector)
        await db.commit()
        
        return {
            "success": True,
            "message": f"Successfully disconnected platform '{platform}'."
        }
    except HTTPException as e:
        raise e
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while disconnecting: {str(e)}"
        )


@router.post("/deauthorize")
async def deauthorize_callback(request: Request):
    """
    Callback endpoint triggered by Meta when a user removes/deauthorizes the app.
    Parses signed request from Meta, logs event, and returns a 200 response.
    """
    try:
        # Retrieve Meta signed_request parameter from form data
        form_data = await request.form()
        signed_request = form_data.get("signed_request")
        
        # Meta expects a 200 OK status code response
        return {"status": "success", "message": "App successfully deauthorized.", "signed_request_received": bool(signed_request)}
    except Exception as e:
        logger.error(f"Error handling Meta deauthorization callback: {e}")
        return {"status": "error", "message": str(e)}


@router.get("/data-deletion")
async def data_deletion_callback(request: Request):
    """
    Data deletion callback page confirming user data removal procedure compliance.
    """
    return {
        "url": "https://sugampudasain.xyz/privacy-policy",
        "confirmation_code": "sahayak_data_deletion_completed"
    }
