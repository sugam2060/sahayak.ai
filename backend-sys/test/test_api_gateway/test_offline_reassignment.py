import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch
from uuid import UUID

from services.api_gateway.routers.chat_routers.handoff_service import handle_user_offline, get_eligible_online_users
from shared.database.schema.users import User, UserRole

class MockCursor:
    def __init__(self, items):
        self.items = items
    def sort(self, *args, **kwargs):
        return self
    async def to_list(self, length=100):
        return self.items

ORG_ID = "11111111-2222-3333-4444-555555555555"
USER_OFFLINE = "33333333-4444-5555-6666-777777777777"

@pytest.mark.asyncio
@patch("shared.database.mongodb.MongoDBManager.get_db")
@patch("services.api_gateway.routers.chat_routers.handoff_service.ChatLockManager")
@patch("services.api_gateway.routers.chat_routers.chats.manager")
@patch("shared.database.engine.SessionLocal")
async def test_handle_user_offline_reassigns_to_online_user(
    mock_session_local,
    mock_manager,
    mock_lock_manager,
    mock_get_db
):
    # Setup AsyncMocks on mock objects to make them awaitable
    mock_lock_manager.release_lock = AsyncMock()
    mock_lock_manager.force_acquire_lock = AsyncMock()
    mock_manager.broadcast = AsyncMock()

    # Setup mocks for MongoDB
    mock_db = MagicMock()
    mock_get_db.return_value = mock_db
    mock_conv = {
        "_id": "conv_id_123",
        "platform": "telegram",
        "organization_id": ORG_ID,
        "bot_id": USER_OFFLINE,
        "user": {"sender_id": "9999"}
    }
    mock_db.conversations.find.return_value = MockCursor([mock_conv])
    mock_db.conversations.update_one = AsyncMock()

    # Setup mocks for PostgreSQL (online users query)
    mock_db_session = AsyncMock()
    mock_session_context = AsyncMock()
    mock_session_context.__aenter__.return_value = mock_db_session
    mock_session_local.return_value = mock_session_context

    mock_online_user = User(
        id=UUID("22222222-3333-4444-5555-666666666666"),
        organization_id=UUID(ORG_ID),
        full_name="Online Agent",
        role=UserRole.AGENT,
        is_active=True
    )
    
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [mock_online_user]
    mock_db_session.execute.return_value = mock_result

    # Mock presence service online list
    with patch("services.api_gateway.routers.presence.presence_service.PresenceService.get_org_online_users", new_callable=AsyncMock) as mock_get_online, \
         patch("services.api_gateway.routers.auth_routers.me.get_user_permissions", new_callable=AsyncMock) as mock_get_perms:
        
        mock_get_online.return_value = ["22222222-3333-4444-5555-666666666666"]
        mock_get_perms.return_value = ["chats"]

        # Call handle_user_offline
        await handle_user_offline(ORG_ID, USER_OFFLINE)

    # Assert lock transfer updates:
    mock_lock_manager.release_lock.assert_called_once_with(ORG_ID, "conv_id_123")
    mock_lock_manager.force_acquire_lock.assert_called_once()
    
    # Assert MongoDB conversation bot_id was updated to online user
    mock_db.conversations.update_one.assert_called_once()
    update_args = mock_db.conversations.update_one.call_args[0]
    assert update_args[0] == {"_id": "conv_id_123"}
    assert update_args[1]["$set"]["bot_id"] == "22222222-3333-4444-5555-666666666666"
    assert update_args[1]["$set"]["ai_assigned"] is False

    # Assert lock update ws event was broadcasted
    mock_manager.broadcast.assert_called_once_with(
        ORG_ID,
        {
            "org_id": ORG_ID,
            "platform": "telegram",
            "sender_id": "9999",
            "type": "chat_lock_update",
            "bot_id": "22222222-3333-4444-5555-666666666666",
            "locker_name": "Online Agent"
        }
    )

@pytest.mark.asyncio
@patch("shared.database.mongodb.MongoDBManager.get_db")
@patch("services.api_gateway.routers.chat_routers.handoff_service.ChatLockManager")
@patch("services.api_gateway.routers.chat_routers.chats.manager")
@patch("shared.database.engine.SessionLocal")
async def test_handle_user_offline_unlocks_when_no_online_users(
    mock_session_local,
    mock_manager,
    mock_lock_manager,
    mock_get_db
):
    # Setup AsyncMocks on mock objects to make them awaitable
    mock_lock_manager.release_lock = AsyncMock()
    mock_lock_manager.force_acquire_lock = AsyncMock()
    mock_manager.broadcast = AsyncMock()

    # Setup mocks for MongoDB
    mock_db = MagicMock()
    mock_get_db.return_value = mock_db
    mock_conv = {
        "_id": "conv_id_123",
        "platform": "telegram",
        "organization_id": ORG_ID,
        "bot_id": USER_OFFLINE,
        "user": {"sender_id": "9999"}
    }
    mock_db.conversations.find.return_value = MockCursor([mock_conv])
    mock_db.conversations.update_one = AsyncMock()

    # Setup mocks for PostgreSQL (no active users)
    mock_db_session = AsyncMock()
    mock_session_context = AsyncMock()
    mock_session_context.__aenter__.return_value = mock_db_session
    mock_session_local.return_value = mock_session_context

    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    mock_db_session.execute.return_value = mock_result

    # Mock presence service online list
    with patch("services.api_gateway.routers.presence.presence_service.PresenceService.get_org_online_users", new_callable=AsyncMock) as mock_get_online:
        mock_get_online.return_value = []

        # Call handle_user_offline
        await handle_user_offline(ORG_ID, USER_OFFLINE)

    # Assert lock is released and conversation unlocked
    mock_lock_manager.release_lock.assert_called_once_with(ORG_ID, "conv_id_123")
    mock_lock_manager.force_acquire_lock.assert_not_called()
    
    # Assert MongoDB conversation bot_id is cleared (None)
    mock_db.conversations.update_one.assert_called_once()
    update_args = mock_db.conversations.update_one.call_args[0]
    assert update_args[0] == {"_id": "conv_id_123"}
    assert update_args[1]["$set"]["bot_id"] is None
    assert update_args[1]["$set"]["ai_assigned"] is False

    # Assert lock release ws event was broadcasted
    mock_manager.broadcast.assert_called_once_with(
        ORG_ID,
        {
            "org_id": ORG_ID,
            "platform": "telegram",
            "sender_id": "9999",
            "type": "chat_lock_update",
            "bot_id": None,
            "locker_name": None
        }
    )
