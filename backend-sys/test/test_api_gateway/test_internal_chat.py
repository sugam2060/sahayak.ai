import pytest
import importlib
from unittest.mock import MagicMock, AsyncMock, patch
from fastapi import status
from uuid import UUID

# Dynamic import to bypass hyphen constraint
service_module = importlib.import_module("services.chatai-service.internal_chat.service")

@pytest.fixture
def override_db(test_client, mock_db_session):
    from services.api_gateway.routers.internal_chat.router import get_db
    async def _get_db():
        yield mock_db_session
    test_client.app.dependency_overrides[get_db] = _get_db
    yield
    test_client.app.dependency_overrides.pop(get_db, None)

@pytest.fixture
def mock_mongo_db():
    mock_db = MagicMock()
    mock_db.internal_conversations = MagicMock()
    mock_db.internal_conversations.find_one = AsyncMock()
    mock_db.internal_conversations.update_one = AsyncMock()
    mock_db.conversations = MagicMock()
    mock_db.conversations.find_one = AsyncMock()
    mock_db.conversations.update_one = AsyncMock()
    with patch("shared.database.mongodb.MongoDBManager.get_db", return_value=mock_db):
        yield mock_db

def test_list_members(test_client, override_db, mock_db_session):
    test_client.cookies.set("access_token", "fake_access_token")
    
    from shared.database.schema.users import User, UserRole
    mock_result = MagicMock()
    mock_result.all.return_value = [
        (UUID("33333333-4444-5555-6666-777777777777"), "Agent Bob", UserRole.AGENT, "bob@example.com")
    ]
    mock_db_session.execute.return_value = mock_result
    
    response = test_client.get("/api/internal-chats/members")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["success"] is True
    assert len(data["members"]) == 1
    assert data["members"][0]["full_name"] == "Agent Bob"

def test_direct_history(test_client, override_db, mock_db_session, mock_mongo_db):
    test_client.cookies.set("access_token", "fake_access_token")
    
    from shared.database.schema.users import User
    mock_user = User(
        id=UUID("33333333-4444-5555-6666-777777777777"),
        organization_id=UUID("11111111-2222-3333-4444-555555555555")
    )
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_user
    mock_db_session.execute.return_value = mock_result
    
    mock_convo = {
        "_id": "convo_123",
        "organization_id": "11111111-2222-3333-4444-555555555555",
        "type": "direct",
        "user_ids": ["22222222-3333-4444-5555-666666666666", "33333333-4444-5555-6666-777777777777"],
        "messages": []
    }
    
    with patch.object(service_module.InternalChatService, "get_or_create_direct_conversation", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_convo
        response = test_client.get("/api/internal-chats/direct/history/33333333-4444-5555-6666-777777777777")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
        assert data["conversation"]["_id"] == "convo_123"

def test_list_groups(test_client, mock_mongo_db):
    test_client.cookies.set("access_token", "fake_access_token")
    
    groups_data = [
        {"_id": "group_123", "organization_id": "org_1", "type": "group", "group_name": "Dev Team"}
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
            
    mock_mongo_db.internal_conversations.find.return_value = MockCursor(groups_data)
    
    response = test_client.get("/api/internal-chats/groups")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["success"] is True
    assert len(data["groups"]) == 1
    assert data["groups"][0]["group_name"] == "Dev Team"

def test_create_group(test_client, mock_mongo_db):
    test_client.cookies.set("access_token", "fake_access_token")
    
    mock_group = {
        "_id": "group_uuid",
        "organization_id": "11111111-2222-3333-4444-555555555555",
        "type": "group",
        "user_ids": ["user_1", "user_2"],
        "group_name": "New Team",
        "messages": []
    }
    
    payload = {
        "name": "New Team",
        "member_ids": ["user_2"]
    }
    
    with patch.object(service_module.InternalChatService, "create_group_conversation", new_callable=AsyncMock) as mock_create, \
         patch("shared.kafka_producer.KafkaProducerPool.send_message", new_callable=AsyncMock) as mock_send:
        mock_create.return_value = mock_group
        response = test_client.post("/api/internal-chats/groups", json=payload)
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
        assert data["group"]["group_name"] == "New Team"
        mock_send.assert_called_once()

def test_respond_customer_request_decline(test_client, override_db, mock_db_session, mock_mongo_db):
    test_client.cookies.set("access_token", "fake_access_token")
    
    mock_convo = {
        "_id": "direct_convo_123",
        "type": "direct",
        "user_ids": ["22222222-3333-4444-5555-666666666666"],
        "messages": [
            {
                "message_id": "req_msg_123",
                "message_type": "customer_chat_request",
                "sender_id": "other_user_uuid",
                "sender_name": "Other User",
                "text": "Please unlock",
                "customer_chat_request": {
                    "platform": "telegram",
                    "sender_id": "99999",
                    "status": "pending"
                }
            }
        ]
    }
    
    mock_mongo_db.internal_conversations.find_one.return_value = mock_convo
    
    payload = {
        "message_id": "req_msg_123",
        "action": "decline"
    }
    
    with patch.object(service_module.InternalChatService, "respond_to_customer_request", new_callable=AsyncMock) as mock_respond, \
         patch("shared.kafka_producer.KafkaProducerPool.send_message", new_callable=AsyncMock) as mock_send:
        mock_respond.return_value = mock_convo
        response = test_client.post("/api/internal-chats/customer-request/respond", json=payload)
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
        assert data["status"] == "declined"
        mock_respond.assert_called_once_with("req_msg_123", "declined")
        mock_send.assert_called_once()

@pytest.fixture
def mock_session_local(mock_db_session):
    mock_sl = MagicMock()
    mock_context = AsyncMock()
    mock_context.__aenter__.return_value = mock_db_session
    mock_sl.return_value = mock_context
    with patch("services.api_gateway.routers.internal_chat.router.SessionLocal", mock_sl):
        yield mock_db_session

def test_websocket_internal_chat_flow(test_client, mock_session_local):
    from shared.database.schema.users import User, UserRole
    # Setup user matches org in DB
    mock_user = User(
        id=UUID("22222222-3333-4444-5555-666666666666"),
        organization_id=UUID("11111111-2222-3333-4444-555555555555"),
        role=UserRole.OWNER,
        full_name="Test User"
    )
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_user
    mock_session_local.execute.return_value = mock_result

    with test_client.websocket_connect(
        "/api/internal-chats/ws/11111111-2222-3333-4444-555555555555?user_id=22222222-3333-4444-5555-666666666666"
    ) as websocket:
        # Send standard chat message event
        websocket.send_json({
            "type": "org",
            "text": "Hello world"
        })

def test_delete_group(test_client, mock_mongo_db):
    test_client.cookies.set("access_token", "fake_access_token")
    
    mock_group = {
        "_id": "group_123",
        "organization_id": "11111111-2222-3333-4444-555555555555",
        "type": "group",
        "user_ids": ["22222222-3333-4444-5555-666666666666"],
        "group_admin_ids": ["22222222-3333-4444-5555-666666666666"],
        "group_name": "Dev Team"
    }
    
    with patch.object(service_module.InternalChatService, "get_group_conversation", new_callable=AsyncMock) as mock_get, \
         patch.object(service_module.InternalChatService, "delete_group_conversation", new_callable=AsyncMock) as mock_delete, \
         patch("shared.kafka_producer.KafkaProducerPool.send_message", new_callable=AsyncMock) as mock_send:
        
        mock_get.return_value = mock_group
        mock_delete.return_value = True
        
        response = test_client.delete("/api/internal-chats/groups/group_123")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
        mock_delete.assert_called_once_with("group_123")
        mock_send.assert_called_once()

