import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from fastapi import status
from shared.database.schema.platform_connectors import PlatformConnector

@pytest.fixture
def mock_mongo_db():
    mock_db = MagicMock()
    mock_db.conversations = MagicMock()
    mock_db.conversations.find_one = AsyncMock()
    with patch("shared.database.mongodb.MongoDBManager.get_db", return_value=mock_db):
        yield mock_db

def test_get_chat_list(test_client, mock_mongo_db):
    chats_data = [
        {"_id": "60c72b2f9b1d8e1f5c8b4567", "organization_id": "org_1", "platform": "telegram"},
        {"_id": "60c72b2f9b1d8e1f5c8b4568", "organization_id": "org_1", "platform": "telegram"}
    ]
    
    class MockCursor:
        def __init__(self, items):
            self.items = items
        def sort(self, *args, **kwargs):
            return self
        def __aiter__(self):
            async def gen():
                for item in self.items:
                    yield item
            return gen()
            
    mock_mongo_db.conversations.find.return_value = MockCursor(chats_data)
    
    response = test_client.get("/api/chats?organization_id=org_1")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["success"] is True
    assert len(data["chats"]) == 2
    assert data["chats"][0]["_id"] == "60c72b2f9b1d8e1f5c8b4567"

def test_get_chat_history_found(test_client, mock_mongo_db):
    mock_conversation = {
        "_id": "60c72b2f9b1d8e1f5c8b4567",
        "organization_id": "org_1",
        "platform": "telegram",
        "user": {"sender_id": 9999, "sender_name": "Alice"},
        "messages": []
    }
    mock_mongo_db.conversations.find_one.return_value = mock_conversation
    
    response = test_client.get("/api/chats/telegram/9999")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["success"] is True
    assert data["chat"]["user"]["sender_name"] == "Alice"

def test_get_chat_history_not_found(test_client, mock_mongo_db):
    mock_mongo_db.conversations.find_one.return_value = None
    response = test_client.get("/api/chats/telegram/9999")
    assert response.status_code == status.HTTP_404_NOT_FOUND

@pytest.fixture
def override_chats_db(test_client, mock_db_session):
    from services.api_gateway.routers.chat_routers.chats import get_db
    async def _get_db():
        yield mock_db_session
    test_client.app.dependency_overrides[get_db] = _get_db
    yield
    test_client.app.dependency_overrides.pop(get_db, None)

def test_send_chat_reply_success(test_client, override_chats_db, mock_db_session, mock_mongo_db):
    # 1. Mock conversation retrieval in MongoDB
    mock_conversation = {
        "_id": "60c72b2f9b1d8e1f5c8b4567",
        "organization_id": "46a42f39-5876-49e2-84b0-725f0733e178",
        "platform": "telegram",
        "chat_id": 8888,
        "user": {"sender_id": 9999}
    }
    mock_mongo_db.conversations.find_one.return_value = mock_conversation
    
    # 2. Mock connector retrieval in PostgreSQL
    mock_connector = PlatformConnector(
        business_id="46a42f39-5876-49e2-84b0-725f0733e178",
        platform="telegram",
        tokens={"bot_token": "123456:ABC-DEF-GHI"}
    )
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [mock_connector]
    mock_db_session.execute.return_value = mock_result
    
    # 3. Call endpoint and assert
    payload = {
        "sender_id": 9999,
        "platform": "telegram",
        "text": "Hello client reply"
    }
    
    import importlib
    chat_svc_module = importlib.import_module("services.chatai-service.chat_service")
    with patch.object(chat_svc_module, "route_outbound_reply", new_callable=AsyncMock) as mock_route:
        response = test_client.post("/api/chats/reply", json=payload)
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["success"] is True
        
        # Verify Kafka routing was triggered with correct parameters
        mock_route.assert_called_once_with(
            org_id="46a42f39-5876-49e2-84b0-725f0733e178",
            bot_name=None,
            bot_token="123456:ABC-DEF-GHI",
            platform="telegram",
            chat_id=8888,
            sender_id=9999,
            text="Hello client reply"
        )

def test_toggle_ai_success(test_client, mock_mongo_db):
    mock_conversation = {
        "_id": "60c72b2f9b1d8e1f5c8b4567",
        "organization_id": "46a42f39-5876-49e2-84b0-725f0733e178",
        "platform": "telegram",
        "chat_id": 8888,
        "user": {"sender_id": 9999}
    }
    mock_mongo_db.conversations.find_one.return_value = mock_conversation
    mock_mongo_db.conversations.update_one = AsyncMock()

    payload = {
        "sender_id": 9999,
        "platform": "telegram",
        "ai_assigned": True
    }

    with patch("services.api_gateway.routers.chat_routers.chats.manager.broadcast", new_callable=AsyncMock) as mock_broadcast:
        response = test_client.post("/api/chats/toggle-ai", json=payload)
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
        assert data["ai_assigned"] is True
        mock_mongo_db.conversations.update_one.assert_called_once()
