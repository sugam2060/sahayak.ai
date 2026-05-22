import os
import sys
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import Optional, Tuple
from uuid import UUID
import httpx
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

# Add backend-sys to sys.path to enable clean shared imports if needed
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from shared.database.schema.platform_connectors import PlatformConnector
# from shared.config import (
#     INSTAGRAM_CLIENT_ID,
#     INSTAGRAM_CLIENT_SECRET,
#     INSTAGRAM_REDIRECT_URI,
#     TELEGRAM_API_BASE_URL,
#     BACKEND_URL,
# )
from shared.config import (
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


# class InstagramConnector(BaseConnector):
#     """Handles OAuth handshake and API details integration for Instagram Graph API accounts."""
# 
#     def get_authorization_url(self, state: str) -> str:
#         if not INSTAGRAM_CLIENT_ID:
#             raise ConnectorError("Instagram configuration is missing: INSTAGRAM_CLIENT_ID not configured.", 500)
#         
#         params = {
#             "client_id": INSTAGRAM_CLIENT_ID,
#             "redirect_uri": INSTAGRAM_REDIRECT_URI,
#             "scope": "user_profile,user_media",
#             "response_type": "code",
#             "state": state
#         }
#         query_string = "&".join(f"{k}={v}" for k, v in params.items())
#         return f"https://api.instagram.com/oauth/authorize?{query_string}"
# 
#     async def connect(self, session: AsyncSession, business_id: UUID, code: str) -> PlatformConnector:
#         # 1. Exchange short-lived token
#         short_tokens = await self._exchange_code(code)
#         short_token = short_tokens.get("access_token")
#         if not short_token:
#             raise ConnectorError("Failed to retrieve short-lived access token from Instagram response.")
# 
#         # 2. Exchange for a long-lived access token (typical for SaaS backends)
#         tokens = await self._exchange_long_lived_token(short_token)
#         long_token = tokens.get("access_token")
#         if not long_token:
#             long_token = short_token  # Fallback to short-lived token if exchange failed
#             tokens = short_tokens
# 
#         # 3. Fetch user profile
#         profile = await self._fetch_account_info(long_token)
#         platform_account_id = profile.get("id")
#         platform_account_name = profile.get("username")
# 
#         if not platform_account_id:
#             raise ConnectorError("Failed to fetch user ID from Instagram profile API.")
# 
#         metadata = {
#             "account_type": profile.get("account_type"),
#             "username": profile.get("username")
#         }
#         return await self.save_connector(
#             session=session,
#             business_id=business_id,
#             platform="instagram",
#             platform_account_id=str(platform_account_id),
#             platform_account_name=platform_account_name,
#             tokens=tokens,
#             platform_metadata=metadata
#         )
# 
#     async def _exchange_code(self, code: str) -> dict:
#         url = "https://api.instagram.com/oauth/access_token"
#         data = {
#             "client_id": INSTAGRAM_CLIENT_ID,
#             "client_secret": INSTAGRAM_CLIENT_SECRET,
#             "grant_type": "authorization_code",
#             "redirect_uri": INSTAGRAM_REDIRECT_URI,
#             "code": code,
#         }
# 
#         async with httpx.AsyncClient() as client:
#             try:
#                 response = await client.post(url, data=data, timeout=15.0)
#                 if response.status_code != 200:
#                     raise ConnectorError(f"Instagram short token exchange failed: {response.text}")
#                 
#                 return response.json()
#             except httpx.HTTPError as e:
#                 raise ConnectorError(f"Network error communicating with Instagram oauth API: {str(e)}", 502)
# 
#     async def _exchange_long_lived_token(self, short_lived_token: str) -> dict:
#         url = "https://graph.instagram.com/access_token"
#         params = {
#             "grant_type": "ig_exchange_token",
#             "client_secret": INSTAGRAM_CLIENT_SECRET,
#             "access_token": short_lived_token
#         }
# 
#         async with httpx.AsyncClient() as client:
#             try:
#                 response = await client.get(url, params=params, timeout=15.0)
#                 if response.status_code != 200:
#                     # Log failure but don't break flow since short lived token still exists
#                     print(f"Failed to exchange Instagram long-lived token: {response.text}")
#                     return {"access_token": short_lived_token}
#                 
#                 resp_data = response.json()
#                 expires_in = resp_data.get("expires_in", 5183944)
#                 resp_data["expires_at"] = (datetime.utcnow() + timedelta(seconds=expires_in)).isoformat()
#                 return resp_data
#             except httpx.HTTPError:
#                 return {"access_token": short_lived_token}
# 
#     async def _fetch_account_info(self, access_token: str) -> dict:
#         url = "https://graph.instagram.com/me"
#         params = {
#             "fields": "id,username,account_type",
#             "access_token": access_token
#         }
# 
#         async with httpx.AsyncClient() as client:
#             try:
#                 response = await client.get(url, params=params, timeout=15.0)
#                 if response.status_code != 200:
#                     raise ConnectorError(f"Instagram profile fetch failed: {response.text}")
#                 return response.json()
#             except httpx.HTTPError as e:
#                 raise ConnectorError(f"Network error fetching Instagram user profile: {str(e)}", 502)


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
        
        print(f"[TelegramConnector] Registering webhook. Target URL: {url} | Webhook: {webhook_url}", flush=True)
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(url, json=payload, timeout=15.0)
            print(f"[TelegramConnector] Webhook registration response. Status: {response.status_code}", flush=True)
        except httpx.TimeoutException as e:
            print(f"[TelegramConnector] Timeout while registering webhook: {str(e)}", flush=True)
            raise ConnectorError("Request to Telegram API timed out while setting up webhook. Please try again.", 502)
        except httpx.RequestError as e:
            print(f"[TelegramConnector] Request error while registering webhook: {str(e)}", flush=True)
            raise ConnectorError(f"Network error communicating with Telegram Bot API to set webhook: {str(e)}", 502)

        try:
            resp_data = response.json()
            print(f"[TelegramConnector] Parsed setWebhook response: {resp_data}", flush=True)
        except Exception as e:
            resp_data = None
            print(f"[TelegramConnector] Failed to parse setWebhook response body: {str(e)}", flush=True)

        if response.status_code != 200 or not resp_data or not resp_data.get("ok"):
            description = resp_data.get("description") if resp_data else "Unknown error"
            print(f"[TelegramConnector] Webhook registration failed: {description}", flush=True)
            raise ConnectorError(f"Failed to register webhook with Telegram: {description}", 400)

    async def disconnect(self, access_token: str) -> None:
        """
        Cleans up resources when disconnecting a Telegram bot (e.g. deletes the webhook).
        """
        url = f"{TELEGRAM_API_BASE_URL}/bot{access_token}/deleteWebhook"
        print(f"[TelegramConnector] Deleting webhook. Target URL: {url}", flush=True)
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(url, timeout=15.0)
            print(f"[TelegramConnector] Webhook deletion response. Status: {response.status_code}", flush=True)
        except Exception as e:
            # We log but do not fail the disconnect process if Telegram is down or token is invalid
            print(f"[TelegramConnector] Failed to delete webhook during disconnect: {str(e)}", flush=True)

    async def _validate_bot_token(self, access_token: str) -> dict:
        url = f"{TELEGRAM_API_BASE_URL}/bot{access_token}/getMe"
        print(f"[TelegramConnector] Attempting to validate bot token. Target URL: {url}", flush=True)
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(url, timeout=15.0)
            print(f"[TelegramConnector] Received response. Status: {response.status_code}", flush=True)
        except httpx.TimeoutException as e:
            print(f"[TelegramConnector] TimeoutException encountered: {str(e)}", flush=True)
            raise ConnectorError("Request to Telegram API timed out. Please try again.", 502)
        except httpx.RequestError as e:
            print(f"[TelegramConnector] RequestError encountered: {str(e)}", flush=True)
            raise ConnectorError(f"Network error communicating with Telegram Bot API: {str(e)}", 502)

        try:
            resp_data = response.json()
            print(f"[TelegramConnector] Parsed JSON response: {resp_data}", flush=True)
        except Exception as e:
            resp_data = None
            print(f"[TelegramConnector] Failed to parse response body as JSON: {str(e)}", flush=True)

        if response.status_code != 200:
            description = resp_data.get("description") if resp_data else None
            if not description:
                description = "Telegram token validation failed. Please check if your bot token is correct."
            print(f"[TelegramConnector] Non-200 response description: {description}", flush=True)
            raise ConnectorError(f"Telegram Bot API error: {description}", 400)

        if resp_data is None or resp_data.get("ok") is False:
            description = resp_data.get("description", "Unknown error") if resp_data else "Unknown error"
            print(f"[TelegramConnector] ok=False response description: {description}", flush=True)
            raise ConnectorError(f"Telegram Bot API error: {description}", 400)

        return resp_data["result"]
