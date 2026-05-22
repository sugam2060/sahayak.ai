import pytest
from unittest.mock import MagicMock
from fastapi import status
from services.api_gateway.routers.chat_routers.telegram_webhook import get_db
from shared.database.schema.platform_connectors import PlatformConnector

@pytest.fixture
def override_webhook_db(test_client, mock_db_session):
    async def _get_db():
        yield mock_db_session
    test_client.app.dependency_overrides[get_db] = _get_db
    yield
    test_client.app.dependency_overrides.pop(get_db, None)

def test_telegram_webhook_with_matching_token(test_client, override_webhook_db, mock_db_session):
    # Mock active telegram connector in database
    mock_connector = PlatformConnector(
        business_id="46a42f39-5876-49e2-84b0-725f0733e178",
        platform="telegram",
        platform_account_name="SahayakTestBot",
        tokens={"bot_token": "123456:ABC-DEF-GHI"}
    )
    
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [mock_connector]
    mock_db_session.execute.return_value = mock_result
    
    payload = {
        "update_id": 987654321,
        "message": {
            "message_id": 42,
            "from": {
                "id": 55555,
                "is_bot": False,
                "first_name": "Test",
                "username": "tester"
            },
            "chat": {
                "id": 66666,
                "type": "private"
            },
            "date": 1620000000,
            "text": "Hello, bot, how are you?"
        }
    }
    
    response = test_client.post("/webhooks/telegram/123456:ABC-DEF-GHI", json=payload)
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"status": "ok"}

def test_telegram_webhook_without_matching_token(test_client, override_webhook_db, mock_db_session):
    # Mock empty platform_connectors database list
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    mock_db_session.execute.return_value = mock_result
    
    payload = {
        "update_id": 987654322,
        "message": {
            "message_id": 43,
            "text": "Hello stranger"
        }
    }
    
    response = test_client.post("/webhooks/telegram/unknown_token_abc", json=payload)
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"status": "ok"}
