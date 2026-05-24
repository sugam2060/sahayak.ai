import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient
from shared.proto import service_pb2

@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.fixture
def mock_db_session():
    """Mock fixture for database AsyncSession."""
    session = AsyncMock()
    session.add = MagicMock()
    # Mocking executing statements returning scalars
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    mock_result.scalars.return_value.first.return_value = None
    mock_result.one_or_none.return_value = None
    session.execute.return_value = mock_result
    return session

@pytest.fixture(autouse=True)
def mock_redis_client():
    """Mock fixture for Redis client, patching all Redis interactions globally."""
    mock_pipe = AsyncMock()
    mock_pipe.get = MagicMock()
    mock_pipe.incr = MagicMock()
    mock_pipe.expire = MagicMock()
    mock_pipe.execute = AsyncMock(return_value=[None, None])
    
    client = AsyncMock()
    mock_pipeline_context = AsyncMock()
    mock_pipeline_context.__aenter__.return_value = mock_pipe
    client.pipeline = MagicMock(return_value=mock_pipeline_context)
    
    client.get.return_value = None
    client.setex.return_value = True
    client.delete.return_value = 1
    client.close = AsyncMock()
    
    with patch("shared.redis_pool.RedisPool.get_client", return_value=client), \
         patch("redis.asyncio.from_url", return_value=client):
        yield client

@pytest.fixture
def mock_auth_stub():
    """Mock fixture for auth gRPC service stub."""
    stub = AsyncMock()
    
    # Setup default mock responses with valid UUID strings
    stub.Register.return_value = service_pb2.RegisterResponse(
        organization_id="11111111-2222-3333-4444-555555555555",
        user_id="22222222-3333-4444-5555-666666666666",
        message="Registration successful"
    )
    stub.Login.return_value = service_pb2.LoginResponse(
        success=True,
        message="Login successful",
        access_token="fake_access_token",
        refresh_token="fake_refresh_token",
        user_id="22222222-3333-4444-5555-666666666666",
        organization_id="11111111-2222-3333-4444-555555555555",
        is_verified=True,
        full_name="Test User",
        organization_name="Test Org",
        organization_slug="test-org",
        email="test@example.com"
    )
    stub.VerifyEmail.return_value = service_pb2.VerifyEmailResponse(
        success=True,
        message="Email verified successfully"
    )
    stub.VerifyAccessToken.return_value = service_pb2.VerifyAccessTokenResponse(
        valid=True,
        message="Token is valid",
        user_id="22222222-3333-4444-5555-666666666666",
        organization_id="11111111-2222-3333-4444-555555555555",
        organization_name="Test Org",
        role="admin"
    )
    stub.RefreshToken.return_value = service_pb2.RefreshTokenResponse(
        success=True,
        message="Tokens refreshed",
        access_token="fake_new_access_token",
        refresh_token="fake_new_refresh_token"
    )
    stub.Logout.return_value = service_pb2.LogoutResponse(
        success=True,
        message="Logged out successfully"
    )
    
    return stub

@pytest.fixture
def test_client(mock_auth_stub):
    """FastAPI TestClient fixture with mocked stub context."""
    from services.api_gateway.main import app
    
    with TestClient(app) as client:
        # Set the mocked stub on app state after lifespan startup runs
        client.app.state.auth_stub = mock_auth_stub
        yield client

@pytest.fixture(autouse=True)
def mock_kafka_producer():
    """Mock fixture for Kafka producer globally."""
    producer_mock = AsyncMock()
    producer_mock.send_message = AsyncMock()
    producer_mock.close = AsyncMock()
    
    with patch("shared.kafka_producer.KafkaProducerPool.send_message", new=producer_mock.send_message), \
         patch("shared.kafka_producer.KafkaProducerPool.close", new=producer_mock.close):
        yield producer_mock

