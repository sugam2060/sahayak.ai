import pytest
import jwt
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import status
from uuid import uuid4
import httpx

from services.api_gateway.routers.connectors.connector_route import get_db
from services.api_gateway.routers.connectors.connector_class import TelegramConnector
from shared.database.schema.platform_connectors import PlatformConnector
from shared.config import JWT_SECRET, JWT_ALGORITHM

@pytest.fixture
def override_db(test_client, mock_db_session):
    from services.api_gateway.routers.connectors.connector_route import get_db as route_get_db
    from services.api_gateway.routers.chat_routers.telegram_webhook import get_db as webhook_get_db
    
    async def _get_db():
        yield mock_db_session
        
    test_client.app.dependency_overrides[route_get_db] = _get_db
    test_client.app.dependency_overrides[webhook_get_db] = _get_db
    yield
    test_client.app.dependency_overrides.pop(route_get_db, None)
    test_client.app.dependency_overrides.pop(webhook_get_db, None)

def test_list_connectors_empty(test_client, override_db, mock_db_session):
    test_client.cookies.set("access_token", "fake_access_token")
    
    # Mock database returning empty list
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    mock_db_session.execute.return_value = mock_result
    
    response = test_client.get("/connectors")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert len(data) == 1  # telegram is listed as disconnected
    assert all(c["status"] == "disconnected" for c in data)

def test_list_connectors_with_active(test_client, override_db, mock_db_session):
    test_client.cookies.set("access_token", "fake_access_token")
    
    # Mock database returning one active Telegram connector
    mock_connector = PlatformConnector(
        id=uuid4(),
        business_id=uuid4(),
        platform="telegram",
        platform_account_name="SahayakTestBot",
        status="active"
    )
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [mock_connector]
    mock_db_session.execute.return_value = mock_result
    
    response = test_client.get("/connectors")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    
    telegram_conn = next(c for c in data if c["platform"] == "telegram")
    assert telegram_conn["status"] == "connected"
    assert telegram_conn["username"] == "SahayakTestBot"

# def test_get_oauth_url_instagram(test_client, mock_auth_stub):
#     test_client.cookies.set("access_token", "fake_access_token")
#     with patch("services.api_gateway.routers.connectors.connector_class.INSTAGRAM_CLIENT_ID", "fake_client_id"):
#         response = test_client.get("/connectors/oauth/url/instagram")
#         assert response.status_code == status.HTTP_200_OK
#         assert response.json()["success"] is True
#         assert "instagram.com/oauth/authorize" in response.json()["url"]
# 
# def test_get_oauth_url_unsupported_platform(test_client):
#     test_client.cookies.set("access_token", "fake_access_token")
#     response = test_client.get("/connectors/oauth/url/unsupported")
#     assert response.status_code == status.HTTP_400_BAD_REQUEST

def test_telegram_connect_success(test_client, override_db, mock_db_session):
    test_client.cookies.set("access_token", "fake_access_token")
    
    success_bot_info = {
        "ok": True,
        "result": {
            "id": 123456789,
            "is_bot": True,
            "first_name": "Sahayak Support",
            "username": "SahayakTestBot"
        }
    }
    
    payload = {
        "bot_username": "SahayakTestBot",
        "access_token": "123456:ABC-DEF-GHI"
    }
    
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get, \
         patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        
        mock_resp_get = MagicMock()
        mock_resp_get.status_code = 200
        mock_resp_get.json.return_value = success_bot_info
        mock_get.return_value = mock_resp_get
        
        mock_resp_post = MagicMock()
        mock_resp_post.status_code = 200
        mock_resp_post.json.return_value = {"ok": True, "result": True}
        mock_post.return_value = mock_resp_post
        
        # We need mock_db_session.execute to return None for existing connector check
        mock_result = MagicMock()
        mock_result.scalars.return_value.first.return_value = None
        mock_db_session.execute.return_value = mock_result
        
        response = test_client.post("/connectors/telegram/connect", json=payload)
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["success"] is True
        mock_post.assert_called_once()  # Webhook registration triggered

def test_telegram_connect_username_mismatch(test_client, override_db, mock_db_session):
    test_client.cookies.set("access_token", "fake_access_token")
    
    success_bot_info = {
        "ok": True,
        "result": {
            "id": 123456789,
            "is_bot": True,
            "first_name": "Sahayak Support",
            "username": "DifferentBotUsername"
        }
    }
    
    payload = {
        "bot_username": "SahayakTestBot",
        "access_token": "123456:ABC-DEF-GHI"
    }
    
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = success_bot_info
        mock_get.return_value = mock_resp
        
        response = test_client.post("/connectors/telegram/connect", json=payload)
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "Username mismatch" in response.json()["detail"]

def test_disconnect_connector_success(test_client, override_db, mock_db_session):
    test_client.cookies.set("access_token", "fake_access_token")
    
    # Mock active Telegram connector
    mock_connector = PlatformConnector(
        id=uuid4(),
        business_id=uuid4(),
        platform="telegram",
        platform_account_name="SahayakTestBot",
        tokens={"bot_token": "123456:ABC-DEF-GHI"},
        status="active"
    )
    mock_result = MagicMock()
    mock_result.scalars.return_value.first.return_value = mock_connector
    mock_db_session.execute.return_value = mock_result
    
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"ok": True, "result": True}
        mock_post.return_value = mock_resp
        
        response = test_client.post("/connectors/disconnect/telegram")
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["success"] is True
        mock_post.assert_called_once()  # Webhook deletion triggered
        mock_db_session.delete.assert_called_with(mock_connector)

def test_disconnect_connector_not_found(test_client, override_db, mock_db_session):
    test_client.cookies.set("access_token", "fake_access_token")
    
    mock_result = MagicMock()
    mock_result.scalars.return_value.first.return_value = None
    mock_db_session.execute.return_value = mock_result
    
    response = test_client.post("/connectors/disconnect/telegram")
    assert response.status_code == status.HTTP_404_NOT_FOUND
