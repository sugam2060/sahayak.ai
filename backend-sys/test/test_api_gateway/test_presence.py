import pytest
import json
from unittest.mock import MagicMock, AsyncMock, patch
from fastapi import status
from fastapi.websockets import WebSocketDisconnect
from uuid import UUID

from shared.database.schema.users import User, UserRole
from services.api_gateway.routers.presence.presence_service import PresenceService
from services.api_gateway.routers.presence.presence_manager import presence_manager

@pytest.fixture(autouse=True)
def setup_redis_pubsub(mock_redis_client):
    mock_pubsub = AsyncMock()
    
    # Mock pubsub.listen as an async generator yielding one expired event and one pubsub event
    async def mock_listen():
        yield {
            "type": "pmessage",
            "channel": "presence:11111111-2222-3333-4444-555555555555",
            "data": '{"userId": "user1", "orgId": "11111111-2222-3333-4444-555555555555", "status": "online", "ts": 1700000000000}'
        }
    
    mock_pubsub.listen = mock_listen
    mock_redis_client.pubsub = MagicMock(return_value=mock_pubsub)
    
    # Configure mock pipeline methods to be MagicMock to avoid RuntimeWarnings
    pipe = mock_redis_client.pipeline.return_value.__aenter__.return_value
    pipe.hset = MagicMock()
    pipe.expire = MagicMock()
    pipe.zadd = MagicMock()
    pipe.sadd = MagicMock()
    pipe.delete = MagicMock()
    pipe.zrem = MagicMock()
    pipe.hgetall = MagicMock()
    
    yield mock_pubsub

@pytest.fixture
def mock_session_local(mock_db_session):
    mock_sl = MagicMock()
    mock_context = AsyncMock()
    mock_context.__aenter__.return_value = mock_db_session
    mock_sl.return_value = mock_context
    with patch("services.api_gateway.routers.presence.router.SessionLocal", mock_sl):
        yield mock_db_session

@pytest.mark.asyncio
async def test_presence_service_set_online(mock_redis_client):
    service = PresenceService(mock_redis_client)
    
    pipe = mock_redis_client.pipeline.return_value.__aenter__.return_value
    
    await service.set_online(
        org_id="org1",
        user_id="user1",
        socket_id="sock1",
        device_type="mobile",
        status="online"
    )
    
    pipe.hset.assert_called_once()
    pipe.expire.assert_called_once()
    pipe.zadd.assert_called_once()
    pipe.sadd.assert_called_once()
    
    mock_redis_client.publish.assert_called_once()
    published_ch = mock_redis_client.publish.call_args[0][0]
    published_msg = json.loads(mock_redis_client.publish.call_args[0][1])
    assert published_ch == "presence:org1"
    assert published_msg["userId"] == "user1"
    assert published_msg["orgId"] == "org1"
    assert published_msg["status"] == "online"

@pytest.mark.asyncio
async def test_presence_service_heartbeat_exists(mock_redis_client):
    service = PresenceService(mock_redis_client)
    
    mock_redis_client.exists.return_value = True
    pipe = mock_redis_client.pipeline.return_value.__aenter__.return_value
    
    await service.heartbeat("org1", "user1", "sock1")
    
    mock_redis_client.exists.assert_called_once_with("presence:org1:user1")
    pipe.hset.assert_called_once()
    pipe.expire.assert_called_once()
    pipe.zadd.assert_called_once()

@pytest.mark.asyncio
async def test_presence_service_heartbeat_not_exists(mock_redis_client):
    service = PresenceService(mock_redis_client)
    
    mock_redis_client.exists.return_value = False
    pipe = mock_redis_client.pipeline.return_value.__aenter__.return_value
    
    await service.heartbeat("org1", "user1", "sock1")
    
    mock_redis_client.exists.assert_called_once_with("presence:org1:user1")
    pipe.hset.assert_not_called()

@pytest.mark.asyncio
async def test_presence_service_set_status_exists(mock_redis_client):
    service = PresenceService(mock_redis_client)
    mock_redis_client.exists.return_value = True
    
    await service.set_status("org1", "user1", "away")
    
    mock_redis_client.hset.assert_called_once_with("presence:org1:user1", "status", "away")
    mock_redis_client.publish.assert_called_once()

@pytest.mark.asyncio
async def test_presence_service_set_offline(mock_redis_client):
    service = PresenceService(mock_redis_client)
    
    # 1. Stays online if other sockets remain
    mock_redis_client.scard.return_value = 1
    await service.set_offline("org1", "user1", "sock1")
    mock_redis_client.srem.assert_called_once_with("presence:user:user1:sockets", "sock1")
    mock_redis_client.publish.assert_not_called()
    
    # Reset mocks
    mock_redis_client.srem.reset_mock()
    
    # 2. Goes offline when 0 sockets remain
    mock_redis_client.scard.return_value = 0
    pipe = mock_redis_client.pipeline.return_value.__aenter__.return_value
    
    await service.set_offline("org1", "user1", "sock1")
    mock_redis_client.srem.assert_called_once_with("presence:user:user1:sockets", "sock1")
    pipe.delete.assert_called_once_with("presence:org1:user1")
    pipe.zrem.assert_called_once_with("presence:org:org1:active", "user1")
    mock_redis_client.publish.assert_called_once()

@pytest.mark.asyncio
async def test_presence_service_handle_expired_key(mock_redis_client):
    service = PresenceService(mock_redis_client)
    pipe = mock_redis_client.pipeline.return_value.__aenter__.return_value
    
    await service.handle_expired_key("org1", "user1")
    pipe.zrem.assert_called_once_with("presence:org:org1:active", "user1")
    pipe.delete.assert_called_once_with("presence:user:user1:sockets")
    mock_redis_client.publish.assert_called_once()

@pytest.mark.asyncio
async def test_presence_service_get_status(mock_redis_client):
    service = PresenceService(mock_redis_client)
    
    mock_redis_client.hgetall.return_value = {
        "status": "away",
        "lastSeen": "1700000000000",
        "socketId": "sock1",
        "deviceType": "web",
        "activeTab": "chat",
        "meta": '{"typing": true}'
    }
    
    status_data = await service.get_status("org1", "user1")
    assert status_data is not None
    assert status_data["status"] == "away"
    assert status_data["lastSeen"] == 1700000000000
    assert status_data["socketId"] == "sock1"
    assert status_data["meta"] == {"typing": True}

@pytest.mark.asyncio
async def test_presence_service_get_org_online_users(mock_redis_client):
    service = PresenceService(mock_redis_client)
    mock_redis_client.zrangebyscore.return_value = ["user1", "user2"]
    
    users = await service.get_org_online_users("org1", 300)
    assert users == ["user1", "user2"]

def test_rest_active_users(test_client, mock_redis_client):
    test_client.cookies.set("access_token", "fake_access_token")
    
    mock_redis_client.zrangebyscore.return_value = ["user1"]
    
    # Pipeline execution returns hgetall output in a list
    pipe = mock_redis_client.pipeline.return_value.__aenter__.return_value
    pipe.execute.return_value = [{
        "status": "online",
        "lastSeen": "1700000000000",
        "socketId": "sock1",
        "deviceType": "web",
        "activeTab": "chat",
        "meta": '{"typing": false}'
    }]
    
    response = test_client.get("/api/presence/active?within_seconds=300")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["success"] is True
    assert len(data["active"]) == 1
    assert data["active"][0]["userId"] == "user1"
    assert data["active"][0]["status"] == "online"

def test_websocket_presence_handshake_unauthorized(test_client, mock_session_local):
    # Setup mock user not found in DB
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_session_local.execute.return_value = mock_result
    
    with test_client.websocket_connect(
        "/api/presence/ws/11111111-2222-3333-4444-555555555555?user_id=22222222-3333-4444-5555-666666666666"
    ) as websocket:
        with pytest.raises(WebSocketDisconnect) as excinfo:
            websocket.receive_json()
        assert excinfo.value.code == 4003

def test_websocket_presence_flow(test_client, mock_session_local, mock_redis_client):
    # Setup user matches org in DB
    mock_user = User(
        id=UUID("22222222-3333-4444-5555-666666666666"),
        organization_id=UUID("11111111-2222-3333-4444-555555555555"),
        role=UserRole.OWNER
    )
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_user
    mock_session_local.execute.return_value = mock_result
    
    # Mock Redis pipeline execution
    pipe = mock_redis_client.pipeline.return_value.__aenter__.return_value
    pipe.execute.return_value = [None, None]
    mock_redis_client.exists.return_value = True

    with test_client.websocket_connect(
        "/api/presence/ws/11111111-2222-3333-4444-555555555555?user_id=22222222-3333-4444-5555-666666666666"
    ) as websocket:
        # Send heartbeat
        websocket.send_json({"event": "presence:heartbeat"})
        
        # Send status update
        websocket.send_json({"event": "presence:status", "status": "busy"})
        
        # Disconnect manually (ends context block)
        pass
