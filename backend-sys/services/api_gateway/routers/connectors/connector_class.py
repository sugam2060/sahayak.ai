import os
import sys
import logging
from abc import ABC, abstractmethod
from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID
import httpx
from urllib.parse import urlencode

logger = logging.getLogger("api_gateway.connector_class")
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

# Add backend-sys to sys.path to enable clean shared imports if needed
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from shared.database.schema.platform_connectors import PlatformConnector
from shared.config import (
    INSTAGRAM_APP_ID,
    INSTAGRAM_APP_SECRET,
    INSTAGRAM_REDIRECT_URI,
    TELEGRAM_API_BASE_URL,
    BACKEND_URL,
)

class ConnectorError(Exception):
    """Custom exception raised during connector handshake or validation operations."""
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class BaseConnector(ABC):
    """Abstract Base Class defining the contract for social media channel connectors."""

    @abstractmethod
    def get_authorization_url(self, state: str) -> str:
        """Generate the authorization redirect URL for OAuth flow."""
        pass

    @abstractmethod
    async def connect(self, session: AsyncSession, business_id: UUID, code: str) -> PlatformConnector:
        """Complete the OAuth callback flow, retrieve tokens, fetch account info, and persist to database."""
        pass

    @classmethod
    async def save_connector(
        cls,
        session: AsyncSession,
        business_id: UUID,
        platform: str,
        platform_account_id: str,
        platform_account_name: Optional[str],
        tokens: dict,
        platform_metadata: Optional[dict] = None
    ) -> PlatformConnector:
        """
        Persists connection details to the platform_connectors table using an upsert pattern.
        Ensures proper database transaction atomicity.
        """
        try:
            # Query if a connector already exists for (business_id, platform)
            stmt = select(PlatformConnector).where(
                PlatformConnector.business_id == business_id,
                PlatformConnector.platform == platform
            )
            result = await session.execute(stmt)
            connector = result.scalars().first()

            if connector:
                # Update existing connection
                connector.platform_account_id = platform_account_id
                connector.platform_account_name = platform_account_name
                connector.tokens = tokens
                connector.platform_metadata = platform_metadata or {}
                connector.status = "active"
                connector.updated_at = func.now()
            else:
                # Create a new connection
                connector = PlatformConnector(
                    business_id=business_id,
                    platform=platform,
                    platform_account_id=platform_account_id,
                    platform_account_name=platform_account_name,
                    tokens=tokens,
                    platform_metadata=platform_metadata or {},
                    status="active"
                )
                session.add(connector)

            # Flush / commit transaction safely
            await session.commit()
            await session.refresh(connector)
            return connector
        except Exception as e:
            await session.rollback()
            raise ConnectorError(f"Database transaction failed while saving connector: {str(e)}", 500)


class InstagramConnector(BaseConnector):
    """Handles OAuth handshake and API integration for Instagram Login for Business."""

    def get_authorization_url(self, state: str) -> str:
        if not INSTAGRAM_APP_ID:
            raise ConnectorError(
                "Instagram configuration is missing: INSTAGRAM_APP_ID not configured.", 500
            )

        scope_str = (
            "instagram_business_basic,"
            "instagram_business_content_publish,"
            "instagram_business_manage_messages,"
            "instagram_business_manage_comments"
        )

        params = {
            "client_id": INSTAGRAM_APP_ID,
            "redirect_uri": INSTAGRAM_REDIRECT_URI,
            "response_type": "code",
            "scope": scope_str,
            "state": state,
        }

        return f"https://www.instagram.com/oauth/authorize?{urlencode(params)}"

    async def connect(
        self, session: AsyncSession, business_id: UUID, code: str
    ) -> PlatformConnector:
        logger.info(
            f"[InstagramConnector] Starting connection handshake. "
            f"business_id: {business_id}, code: {code[:10]}..."
        )

        # Step 1: Exchange code → short-lived token
        short_tokens = await self._exchange_code(code)
        short_token = short_tokens.get("access_token")
        app_scoped_user_id = str(short_tokens.get("user_id", ""))

        if not short_token or not app_scoped_user_id:
            raise ConnectorError(
                "Failed to retrieve access token or user ID from Instagram response."
            )

        logger.info(
            f"[InstagramConnector] Short-lived token exchanged. "
            f"app_scoped_user_id: {app_scoped_user_id}"
        )

        # Step 2: Exchange short-lived → long-lived token (~60 days)
        tokens = await self._exchange_long_lived_token(short_token)

        # Step 3: Fetch the real Instagram Business Account ID.
        #
        # CRITICAL: The token exchange returns an app-scoped user ID (ASID), which is
        # app-specific and NOT what Meta sends as entry.id / recipient.id in webhooks.
        # Webhooks always use the Instagram Business Account ID (IGBA ID).
        # We MUST store the IGBA ID as platform_account_id or connector lookup will
        # always fail and all incoming DMs will be dumped.
        #
        # The IGBA ID comes from GET graph.instagram.com/v21.0/me using the access token.
        profile = await self._fetch_profile(tokens["access_token"])
        igba_id = profile.get("id")
        username = profile.get("username")

        # Hard failure — if we can't get the real IGBA ID, storing the ASID would
        # silently break all webhook matching. Surface this immediately at connect time.
        if not igba_id:
            raise ConnectorError(
                "Failed to fetch Instagram Business Account ID from /me endpoint. "
                "Cannot store connector without the correct platform_account_id."
            )

        if not username:
            logger.warning(
                "[InstagramConnector] Username not returned from /me, "
                f"falling back to app_scoped_user_id: {app_scoped_user_id}"
            )
            username = app_scoped_user_id

        logger.info(
            f"[InstagramConnector] Resolved IGBA ID: {igba_id}, "
            f"username: {username} (ASID was: {app_scoped_user_id})"
        )

        # Preserve both IDs in the stored token blob.
        # - access_token  → used for all Graph API calls (send DMs, fetch user profiles)
        # - user_id       → IGBA ID, matches webhook recipient.id
        # - app_scoped_user_id → ASID from OAuth, kept for reference/debugging
        tokens["user_id"] = igba_id
        tokens["app_scoped_user_id"] = app_scoped_user_id

        metadata = {
            "account_type": "BUSINESS",
            "username": username,
            "app_scoped_user_id": app_scoped_user_id,
        }

        logger.info("[InstagramConnector] Persisting connector to database...")
        connector = await self.save_connector(
            session=session,
            business_id=business_id,
            platform="instagram",
            platform_account_id=igba_id,       # ← IGBA ID, matches webhook recipient.id
            platform_account_name=username,
            tokens=tokens,
            platform_metadata=metadata,
        )
        logger.info(
            f"[InstagramConnector] Connection completed. connector_id: {connector.id}"
        )
        return connector

    async def _exchange_code(self, code: str) -> dict:
        """Exchange authorization code for a short-lived access token."""
        url = "https://api.instagram.com/oauth/access_token"
        data = {
            "client_id": INSTAGRAM_APP_ID,
            "client_secret": INSTAGRAM_APP_SECRET,
            "grant_type": "authorization_code",
            "redirect_uri": INSTAGRAM_REDIRECT_URI,
            "code": code,
        }

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(url, data=data, timeout=15.0)
                if response.status_code != 200:
                    raise ConnectorError(
                        f"Instagram short token exchange failed: {response.text}"
                    )
                return response.json()
            except httpx.HTTPError as e:
                raise ConnectorError(
                    f"Network error during Instagram OAuth: {str(e)}", 502
                )

    async def _exchange_long_lived_token(self, short_lived_token: str) -> dict:
        """Exchange short-lived token for a long-lived token (~60 days)."""
        url = "https://graph.instagram.com/access_token"
        params = {
            "grant_type": "ig_exchange_token",
            "client_secret": INSTAGRAM_APP_SECRET,
            "access_token": short_lived_token,
        }

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(url, params=params, timeout=15.0)
                if response.status_code != 200:
                    logger.warning(
                        f"[InstagramConnector] Long-lived token exchange failed: "
                        f"{response.text}. Falling back to short-lived token."
                    )
                    return {"access_token": short_lived_token}

                resp_data = response.json()
                expires_in = resp_data.get("expires_in", 5183944)
                resp_data["expires_at"] = (
                    datetime.now(timezone.utc) + timedelta(seconds=expires_in)
                ).isoformat()
                return resp_data

            except httpx.HTTPError as e:
                logger.warning(
                    f"[InstagramConnector] Network error during long-lived token exchange: "
                    f"{str(e)}. Falling back to short-lived token."
                )
                return {"access_token": short_lived_token}

    async def _fetch_profile(self, access_token: str) -> dict:
        """
        Fetch Instagram Business Account profile via GET /me.

        Returns dict with:
          - 'id'       → IGBA ID (used by Meta webhooks as entry.id / recipient.id)
          - 'username' → human-readable account name

        Returns empty dict on failure — caller is responsible for treating
        a missing 'id' as a hard error (do not fall back to ASID silently).
        """
        url = "https://graph.instagram.com/v21.0/me"
        params = {
            "fields": "id,username,account_type",
            "access_token": access_token,
        }

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(url, params=params, timeout=15.0)
                if response.status_code == 200:
                    data = response.json()
                    logger.info(f"[InstagramConnector] GET /me response: {data}")
                    return data
                logger.warning(
                    f"[InstagramConnector] GET /me returned "
                    f"{response.status_code}: {response.text}"
                )
            except httpx.HTTPError as e:
                logger.warning(
                    f"[InstagramConnector] GET /me network error: {str(e)}"
                )

        return {}


class TelegramConnector:
    """Handles Telegram bot credentials validation and integration."""

    async def connect(
        self,
        session: AsyncSession,
        business_id: UUID,
        bot_username: str,
        access_token: str
    ) -> PlatformConnector:
        # 1. Validate credentials with Telegram Bot API
        bot_info = await self._validate_bot_token(access_token)
        
        api_username = bot_info.get("username", "")
        # Normalize and compare usernames
        norm_input = bot_username.lower().replace("@", "").strip()
        norm_api = api_username.lower().replace("@", "").strip()
        
        if norm_input != norm_api:
            raise ConnectorError(
                f"Username mismatch: The bot token provided is registered to username @{api_username}, but @{bot_username} was entered.",
                400
            )

        # 2. Register Webhook URL with Telegram Bot API
        await self._register_webhook(access_token)

        platform_account_id = str(bot_info["id"])
        platform_account_name = api_username or bot_info.get("first_name")

        tokens = {"bot_token": access_token}
        metadata = {
            "first_name": bot_info.get("first_name"),
            "can_join_groups": bot_info.get("can_join_groups"),
            "can_read_all_group_messages": bot_info.get("can_read_all_group_messages")
        }

        # 3. Save Telegram connection details into database using BaseConnector classmethod
        return await BaseConnector.save_connector(
            session=session,
            business_id=business_id,
            platform="telegram",
            platform_account_id=platform_account_id,
            platform_account_name=platform_account_name,
            tokens=tokens,
            platform_metadata=metadata
        )

    async def _register_webhook(self, access_token: str) -> None:
        webhook_url = f"{BACKEND_URL}/webhooks/telegram/{access_token}"
        url = f"{TELEGRAM_API_BASE_URL}/bot{access_token}/setWebhook"
        payload = {"url": webhook_url}
        
        # Mask the token in logged URLs
        masked_token = access_token[:8] + "..." + access_token[-4:] if len(access_token) > 12 else "***"
        masked_url = f"{TELEGRAM_API_BASE_URL}/bot{masked_token}/setWebhook"
        masked_webhook_url = f"{BACKEND_URL}/webhooks/telegram/{masked_token}"
        
        logger.debug(f"[TelegramConnector] Registering webhook. Target URL: {masked_url} | Webhook: {masked_webhook_url}")
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(url, json=payload, timeout=15.0)
            logger.debug(f"[TelegramConnector] Webhook registration response. Status: {response.status_code}")
        except httpx.TimeoutException as e:
            logger.error(f"[TelegramConnector] Timeout while registering webhook: {str(e)}")
            raise ConnectorError("Request to Telegram API timed out while setting up webhook. Please try again.", 502)
        except httpx.RequestError as e:
            logger.error(f"[TelegramConnector] Request error while registering webhook: {str(e)}")
            raise ConnectorError(f"Network error communicating with Telegram Bot API to set webhook: {str(e)}", 502)

        try:
            resp_data = response.json()
            logger.debug(f"[TelegramConnector] Parsed setWebhook response: {resp_data}")
        except Exception as e:
            resp_data = None
            logger.error(f"[TelegramConnector] Failed to parse setWebhook response body: {str(e)}")

        if response.status_code != 200 or not resp_data or not resp_data.get("ok"):
            description = resp_data.get("description") if resp_data else "Unknown error"
            logger.error(f"[TelegramConnector] Webhook registration failed: {description}")
            raise ConnectorError(f"Failed to register webhook with Telegram: {description}", 400)

    async def disconnect(self, access_token: str) -> None:
        """
        Cleans up resources when disconnecting a Telegram bot (e.g. deletes the webhook).
        """
        url = f"{TELEGRAM_API_BASE_URL}/bot{access_token}/deleteWebhook"
        masked_token = access_token[:8] + "..." + access_token[-4:] if len(access_token) > 12 else "***"
        masked_url = f"{TELEGRAM_API_BASE_URL}/bot{masked_token}/deleteWebhook"
        
        logger.debug(f"[TelegramConnector] Deleting webhook. Target URL: {masked_url}")
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(url, timeout=15.0)
            logger.debug(f"[TelegramConnector] Webhook deletion response. Status: {response.status_code}")
        except Exception as e:
            # We log but do not fail the disconnect process if Telegram is down or token is invalid
            logger.error(f"[TelegramConnector] Failed to delete webhook during disconnect: {str(e)}")

    async def _validate_bot_token(self, access_token: str) -> dict:
        url = f"{TELEGRAM_API_BASE_URL}/bot{access_token}/getMe"
        masked_token = access_token[:8] + "..." + access_token[-4:] if len(access_token) > 12 else "***"
        masked_url = f"{TELEGRAM_API_BASE_URL}/bot{masked_token}/getMe"
        
        logger.debug(f"[TelegramConnector] Attempting to validate bot token. Target URL: {masked_url}")
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(url, timeout=15.0)
            logger.debug(f"[TelegramConnector] Received response. Status: {response.status_code}")
        except httpx.TimeoutException as e:
            logger.error(f"[TelegramConnector] TimeoutException encountered: {str(e)}")
            raise ConnectorError("Request to Telegram API timed out. Please try again.", 502)
        except httpx.RequestError as e:
            logger.error(f"[TelegramConnector] RequestError encountered: {str(e)}")
            raise ConnectorError(f"Network error communicating with Telegram Bot API: {str(e)}", 502)

        try:
            resp_data = response.json()
            logger.debug(f"[TelegramConnector] Parsed JSON response: {resp_data}")
        except Exception as e:
            resp_data = None
            logger.error(f"[TelegramConnector] Failed to parse response body as JSON: {str(e)}")

        if response.status_code != 200:
            description = resp_data.get("description") if resp_data else None
            if not description:
                description = "Telegram token validation failed. Please check if your bot token is correct."
            logger.error(f"[TelegramConnector] Non-200 response description: {description}")
            raise ConnectorError(f"Telegram Bot API error: {description}", 400)

        if resp_data is None or resp_data.get("ok") is False:
            description = resp_data.get("description", "Unknown error") if resp_data else "Unknown error"
            logger.error(f"[TelegramConnector] ok=False response description: {description}")
            raise ConnectorError(f"Telegram Bot API error: {description}", 400)

        return resp_data["result"]
