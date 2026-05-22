import pytest
import uuid
import json
import jwt
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.exc import IntegrityError

from shared.proto import service_pb2
from shared.database.schema import Organization, User, UserRole, RefreshToken, AuditEventType
from shared.config import JWT_SECRET, JWT_ALGORITHM

from services.auth_service.registration import handle_registration
from services.auth_service.login import handle_login
from services.auth_service.verification import handle_verify_email
from services.auth_service.verify_token import handle_verify_access_token
from services.auth_service.refresh import handle_refresh_token, force_user_logout
from services.auth_service.logout import handle_logout

@pytest.fixture
def mock_db_session():
    """Fixture for creating a mock DB AsyncSession."""
    session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    mock_result.scalars.return_value.first.return_value = None
    mock_result.scalar_one.return_value = None
    mock_result.scalar_one_or_none.return_value = None
    mock_result.one_or_none.return_value = None
    session.execute.return_value = mock_result
    
    # support context manager for session.begin()
    session.begin = MagicMock()
    session.begin.return_value = AsyncMock()
    return session

@pytest.fixture
def patch_session_local(mock_db_session):
    """Fixture to patch SessionLocal in all handlers to use mock_db_session."""
    mock_maker = MagicMock()
    mock_context = AsyncMock()
    mock_maker.return_value = mock_context
    mock_context.__aenter__.return_value = mock_db_session
    
    with patch("services.auth_service.registration.SessionLocal", mock_maker), \
         patch("services.auth_service.login.SessionLocal", mock_maker), \
         patch("services.auth_service.refresh.SessionLocal", mock_maker), \
         patch("services.auth_service.verification.SessionLocal", mock_maker), \
         patch("services.auth_service.verify_token.SessionLocal", mock_maker), \
         patch("services.auth_service.audit_utils.SessionLocal", mock_maker):
        yield mock_db_session, mock_maker

@pytest.fixture
def patch_redis(mock_redis_client):
    """Fixture to provide mock_redis_client as patch_redis."""
    yield mock_redis_client, MagicMock()

@pytest.fixture
def patch_audit_logs():
    """Fixture to mock audit logging and prevent background thread issues."""
    with patch("services.auth_service.login.log_audit_event", new_callable=AsyncMock) as mock_login_audit, \
         patch("services.auth_service.refresh.log_audit_event", new_callable=AsyncMock) as mock_refresh_audit:
        yield mock_login_audit, mock_refresh_audit

@pytest.fixture
def patch_auth_utils():
    """Fixture to patch hash_password and verify_password for speed."""
    with patch("services.auth_service.registration.hash_password", side_effect=lambda x: f"hashed_{x}") as mock_hash, \
         patch("services.auth_service.login.verify_password", side_effect=lambda plain, hashed: hashed == f"hashed_{plain}") as mock_verify:
        yield mock_hash, mock_verify

# --- handle_registration Tests ---

@pytest.mark.asyncio
async def test_handle_registration_success(patch_session_local, mock_redis_client, patch_auth_utils, mock_kafka_producer):
    db_session, _ = patch_session_local
    
    request = service_pb2.RegisterRequest(
        org_name="New Org",
        org_slug="new-org",
        user_full_name="Alice Smith",
        user_email="alice@example.com",
        user_password="password123"
    )
    
    # Mock successful insert and flush to set ids
    def mock_flush_side_effect():
        # Find the org and user added to the session and assign ids
        for item in db_session.add.call_args_list:
            obj = item[0][0]
            if isinstance(obj, Organization):
                obj.id = uuid.UUID("11111111-2222-3333-4444-555555555555")
            elif isinstance(obj, User):
                obj.id = uuid.UUID("66666666-7777-8888-9999-000000000000")
    
    db_session.flush.side_effect = mock_flush_side_effect
    
    resp = await handle_registration(request)
    
    assert resp.organization_id == "11111111-2222-3333-4444-555555555555"
    assert resp.user_id == "66666666-7777-8888-9999-000000000000"
    assert "Registration successful" in resp.message
    
    # Verify redis tokens were set
    assert mock_redis_client.setex.call_count == 2
    
    # Verify Kafka email message published
    mock_kafka_producer.send_message.assert_called_once()
    kwargs = mock_kafka_producer.send_message.call_args[1]
    assert kwargs["topic"] == "mail-events"
    val = kwargs["value"]
    assert val["email"] == "alice@example.com"
    assert "Verify your Sahayak Account" in val["subject"]
    assert "verify/user/" in val["html_content"]

@pytest.mark.asyncio
async def test_handle_registration_slug_exists(patch_session_local):
    db_session, _ = patch_session_local
    
    request = service_pb2.RegisterRequest(
        org_name="Duplicate Slug Org",
        org_slug="dup-slug",
        user_full_name="Alice Smith",
        user_email="alice@example.com",
        user_password="password123"
    )
    
    # Raise IntegrityError with organizations_slug_key
    db_session.flush.side_effect = IntegrityError(None, None, Exception("organizations_slug_key"))
    
    with pytest.raises(ValueError) as exc_info:
        await handle_registration(request)
        
    assert "slug 'dup-slug' is already taken" in str(exc_info.value)
    db_session.rollback.assert_called_once()

@pytest.mark.asyncio
async def test_handle_registration_email_exists(patch_session_local):
    db_session, _ = patch_session_local
    
    request = service_pb2.RegisterRequest(
        org_name="Unique Org",
        org_slug="unique-org",
        user_full_name="Alice Smith",
        user_email="dup@example.com",
        user_password="password123"
    )
    
    # Raise IntegrityError with ix_users_email
    db_session.flush.side_effect = IntegrityError(None, None, Exception("ix_users_email"))
    
    with pytest.raises(ValueError) as exc_info:
        await handle_registration(request)
        
    assert "email 'dup@example.com' is already registered" in str(exc_info.value)
    db_session.rollback.assert_called_once()

@pytest.mark.asyncio
async def test_handle_registration_other_integrity_error(patch_session_local):
    db_session, _ = patch_session_local
    
    request = service_pb2.RegisterRequest(
        org_name="Unique Org",
        org_slug="unique-org",
        user_full_name="Alice Smith",
        user_email="alice@example.com",
        user_password="password123"
    )
    
    db_session.flush.side_effect = IntegrityError(None, None, Exception("some other constraint"))
    
    with pytest.raises(ValueError) as exc_info:
        await handle_registration(request)
        
    assert "database integrity error occurred" in str(exc_info.value)
    db_session.rollback.assert_called_once()

# --- handle_login Tests ---

@pytest.mark.asyncio
async def test_handle_login_success(patch_session_local, mock_redis_client, patch_auth_utils, patch_audit_logs):
    db_session, _ = patch_session_local
    mock_login_audit, _ = patch_audit_logs
    
    request = service_pb2.LoginRequest(
        email="john@example.com",
        password="securepassword",
        ip_address="127.0.0.1",
        user_agent="pytest"
    )
    
    # Cache miss
    mock_redis_client.get.return_value = None
    
    # DB response setup
    org = Organization(id=uuid.UUID("11111111-2222-3333-4444-555555555555"), name="My Org", slug="my-org")
    user = User(
        id=uuid.UUID("66666666-7777-8888-9999-000000000000"),
        full_name="John Doe",
        email="john@example.com",
        password_hash="hashed_securepassword",
        role=UserRole.OWNER,
        organization_id=org.id,
        is_verified=True,
        is_active=True,
        failed_login_attempts=0,
        locked_until=None
    )
    
    mock_result = MagicMock()
    mock_result.one_or_none.return_value = (user, org)
    db_session.execute.return_value = mock_result
    
    # Make user fetch for updating login attempts return the user object
    db_session.execute.return_value.scalar_one.return_value = user
    db_session.execute.return_value.scalar_one_or_none.return_value = None
    
    resp = await handle_login(request)
    
    assert resp.success is True
    assert resp.email == "john@example.com"
    assert resp.user_id == str(user.id)
    assert resp.organization_id == str(org.id)
    assert resp.access_token is not None
    assert resp.refresh_token is not None
    
    # Verify session caching in Redis
    assert mock_redis_client.setex.call_count >= 2

@pytest.mark.asyncio
async def test_handle_login_cached_success(patch_session_local, mock_redis_client, patch_auth_utils, patch_audit_logs):
    db_session, _ = patch_session_local
    
    request = service_pb2.LoginRequest(
        email="john@example.com",
        password="securepassword",
        ip_address="127.0.0.1",
        user_agent="pytest"
    )
    
    # Cache hit
    cached_user_data = {
        "id": "66666666-7777-8888-9999-000000000000",
        "full_name": "John Doe",
        "email": "john@example.com",
        "password_hash": "hashed_securepassword",
        "role": "OWNER",
        "organization_id": "11111111-2222-3333-4444-555555555555",
        "organization_name": "My Org",
        "organization_slug": "my-org",
        "is_verified": True,
        "is_active": True,
        "failed_login_attempts": 0,
        "locked_until": None
    }
    mock_redis_client.get.return_value = json.dumps(cached_user_data)
    
    # Mock DB user fetch for updates
    user = User(
        id=uuid.UUID("66666666-7777-8888-9999-000000000000"),
        failed_login_attempts=0
    )
    mock_result = MagicMock()
    mock_result.scalar_one.return_value = user
    mock_result.scalar_one_or_none.return_value = None
    db_session.execute.return_value = mock_result
    
    resp = await handle_login(request)
    
    assert resp.success is True
    assert resp.email == "john@example.com"
    # Ensure no SELECT queries to fetch user & org were made since we had a cache hit
    assert db_session.execute.call_count == 2  # 1 to fetch user for updating login stats, 1 to fetch refresh token

@pytest.mark.asyncio
async def test_handle_login_locked(patch_session_local, mock_redis_client):
    request = service_pb2.LoginRequest(
        email="locked@example.com",
        password="password123"
    )
    
    future_time = (datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat()
    cached_user_data = {
        "id": "66666666-7777-8888-9999-000000000000",
        "full_name": "Locked User",
        "email": "locked@example.com",
        "password_hash": "hashed_password",
        "role": "AGENT",
        "organization_id": "11111111-2222-3333-4444-555555555555",
        "organization_name": "My Org",
        "organization_slug": "my-org",
        "is_verified": True,
        "is_active": True,
        "failed_login_attempts": 5,
        "locked_until": future_time
    }
    mock_redis_client.get.return_value = json.dumps(cached_user_data)
    
    resp = await handle_login(request)
    
    assert resp.success is False
    assert "temporarily locked" in resp.message

@pytest.mark.asyncio
async def test_handle_login_password_mismatch(patch_session_local, mock_redis_client, patch_auth_utils, patch_audit_logs):
    db_session, _ = patch_session_local
    
    request = service_pb2.LoginRequest(
        email="john@example.com",
        password="wrong_password",
        ip_address="127.0.0.1",
        user_agent="pytest"
    )
    
    cached_user_data = {
        "id": "66666666-7777-8888-9999-000000000000",
        "full_name": "John Doe",
        "email": "john@example.com",
        "password_hash": "hashed_correct_password",
        "role": "OWNER",
        "organization_id": "11111111-2222-3333-4444-555555555555",
        "organization_name": "My Org",
        "organization_slug": "my-org",
        "is_verified": True,
        "is_active": True,
        "failed_login_attempts": 0,
        "locked_until": None
    }
    mock_redis_client.get.return_value = json.dumps(cached_user_data)
    
    # Mock user object update
    user = User(
        id=uuid.UUID("66666666-7777-8888-9999-000000000000"),
        failed_login_attempts=0,
        locked_until=None
    )
    mock_result = MagicMock()
    mock_result.scalar_one.return_value = user
    db_session.execute.return_value = mock_result
    
    resp = await handle_login(request)
    
    assert resp.success is False
    assert resp.message == "Invalid email or password."
    assert user.failed_login_attempts == 1
    
    # Check cache invalidation
    mock_redis_client.delete.assert_called_with(f"user_auth_cache:{request.email}")

@pytest.mark.asyncio
async def test_handle_login_unverified_email(patch_session_local, mock_redis_client, patch_auth_utils, mock_kafka_producer):
    request = service_pb2.LoginRequest(
        email="unverified@example.com",
        password="password123"
    )
    
    cached_user_data = {
        "id": "66666666-7777-8888-9999-000000000000",
        "full_name": "Unverified User",
        "email": "unverified@example.com",
        "password_hash": "hashed_password123",
        "role": "AGENT",
        "organization_id": "11111111-2222-3333-4444-555555555555",
        "organization_name": "My Org",
        "organization_slug": "my-org",
        "is_verified": False,
        "is_active": True,
        "failed_login_attempts": 0,
        "locked_until": None
    }
    mock_redis_client.get.side_effect = lambda key: json.dumps(cached_user_data) if "user_auth_cache" in key else None
    
    resp = await handle_login(request)
    
    assert resp.success is False
    assert resp.is_verified is False
    assert "New link sent" in resp.message
    
    # Verify Kafka email message published
    mock_kafka_producer.send_message.assert_called_once()
    kwargs = mock_kafka_producer.send_message.call_args[1]
    assert kwargs["topic"] == "mail-events"
    val = kwargs["value"]
    assert val["email"] == "unverified@example.com"
    assert "Verify your Sahayak Account" in val["subject"]
    assert "verify/user/" in val["html_content"]

# --- handle_verify_email Tests ---

@pytest.mark.asyncio
async def test_handle_verify_email_success(patch_session_local, mock_redis_client):
    db_session, _ = patch_session_local
    
    request = service_pb2.VerifyEmailRequest(token="valid_token")
    mock_redis_client.get.return_value = "verify@example.com"
    
    resp = await handle_verify_email(request)
    
    assert resp.success is True
    assert "verified successfully" in resp.message
    
    # Check DB update was executed
    assert db_session.execute.call_count == 1
    
    # Check Redis cleanup
    assert mock_redis_client.delete.call_count == 2

@pytest.mark.asyncio
async def test_handle_verify_email_invalid_token(patch_session_local, mock_redis_client):
    request = service_pb2.VerifyEmailRequest(token="invalid_token")
    mock_redis_client.get.return_value = None
    
    resp = await handle_verify_email(request)
    
    assert resp.success is False
    assert "Invalid or expired" in resp.message

# --- handle_verify_access_token Tests ---

@pytest.mark.asyncio
async def test_handle_verify_access_token_success(patch_session_local, mock_redis_client):
    # Mock access token decoding
    payload = {
        "sub": "66666666-7777-8888-9999-000000000000",
        "org": "11111111-2222-3333-4444-555555555555",
        "role": "OWNER"
    }
    
    token = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
    request = service_pb2.VerifyAccessTokenRequest(access_token=token)
    
    session_data = {
        "user_id": "66666666-7777-8888-9999-000000000000",
        "full_name": "John Doe",
        "role": "OWNER",
        "organization_id": "11111111-2222-3333-4444-555555555555",
        "organization_name": "My Org",
        "organization_slug": "my-org"
    }
    mock_redis_client.get.return_value = json.dumps(session_data)
    
    resp = await handle_verify_access_token(request)
    
    assert resp.valid is True
    assert resp.user_id == session_data["user_id"]
    assert resp.full_name == session_data["full_name"]
    assert resp.organization_name == session_data["organization_name"]

@pytest.mark.asyncio
async def test_handle_verify_access_token_db_fallback(patch_session_local, mock_redis_client):
    db_session, _ = patch_session_local
    
    payload = {
        "sub": "66666666-7777-8888-9999-000000000000",
        "org": "11111111-2222-3333-4444-555555555555",
        "role": "OWNER"
    }
    token = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
    request = service_pb2.VerifyAccessTokenRequest(access_token=token)
    
    mock_redis_client.get.return_value = None  # Cache miss
    
    # DB response setup
    org = Organization(id=uuid.UUID("11111111-2222-3333-4444-555555555555"), name="My Org", slug="my-org")
    user = User(
        id=uuid.UUID("66666666-7777-8888-9999-000000000000"),
        full_name="John Doe",
        role=UserRole.OWNER,
        is_active=True,
        is_verified=True
    )
    mock_result = MagicMock()
    mock_result.one_or_none.return_value = (user, org)
    db_session.execute.return_value = mock_result
    
    resp = await handle_verify_access_token(request)
    
    assert resp.valid is True
    assert resp.user_id == str(user.id)
    assert resp.organization_name == org.name
    
    # Verify session was cached back in Redis
    assert mock_redis_client.setex.call_count == 1

@pytest.mark.asyncio
async def test_handle_verify_access_token_invalid():
    request = service_pb2.VerifyAccessTokenRequest(access_token="invalid_token_string")
    resp = await handle_verify_access_token(request)
    assert resp.valid is False
    assert "Invalid or expired" in resp.message

# --- handle_refresh_token Tests ---

@pytest.mark.asyncio
async def test_handle_refresh_token_success(patch_session_local, patch_redis, patch_audit_logs):
    db_session, _ = patch_session_local
    mock_redis_client, _ = patch_redis
    
    user_id = "66666666-7777-8888-9999-000000000000"
    org_id = "11111111-2222-3333-4444-555555555555"
    
    refresh_token_str = jwt.encode({"sub": user_id}, JWT_SECRET, algorithm=JWT_ALGORITHM)
    request = service_pb2.RefreshTokenRequest(
        refresh_token=refresh_token_str,
        ip_address="127.0.0.1",
        user_agent="pytest"
    )
    
    # Mock DB findings
    db_rt = RefreshToken(
        user_id=uuid.UUID(user_id),
        organization_id=uuid.UUID(org_id),
        token_hash=refresh_token_str,
        revoked=False,
        expire_at=(datetime.now(timezone.utc) + timedelta(days=1)).replace(tzinfo=None)
    )
    user = User(
        id=uuid.UUID(user_id),
        organization_id=uuid.UUID(org_id),
        role=UserRole.OWNER,
        is_active=True
    )
    
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.side_effect = [db_rt, user]
    db_session.execute.return_value = mock_result
    
    resp = await handle_refresh_token(request)
    
    assert resp.success is True
    assert resp.access_token is not None
    assert resp.refresh_token is not None
    assert resp.user_id == user_id
    assert resp.organization_id == org_id

@pytest.mark.asyncio
async def test_handle_refresh_token_revoked(patch_session_local, patch_redis):
    db_session, _ = patch_session_local
    mock_redis_client, _ = patch_redis
    
    user_id = "66666666-7777-8888-9999-000000000000"
    refresh_token_str = jwt.encode({"sub": user_id}, JWT_SECRET, algorithm=JWT_ALGORITHM)
    request = service_pb2.RefreshTokenRequest(refresh_token=refresh_token_str)
    
    db_rt = RefreshToken(
        user_id=uuid.UUID(user_id),
        token_hash=refresh_token_str,
        revoked=True,
        expire_at=(datetime.now(timezone.utc) + timedelta(days=1)).replace(tzinfo=None)
    )
    
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = db_rt
    db_session.execute.return_value = mock_result
    
    resp = await handle_refresh_token(request)
    
    assert resp.success is False
    assert "revoked" in resp.message
    
    # Check force_user_logout clearing Redis
    assert mock_redis_client.delete.call_count == 1
    assert db_session.execute.call_count >= 2  # includes delete in force_user_logout

# --- handle_logout Tests ---

@pytest.mark.asyncio
async def test_handle_logout_success(patch_session_local, patch_redis):
    user_id = "66666666-7777-8888-9999-000000000000"
    access_token = jwt.encode({"sub": user_id}, JWT_SECRET, algorithm=JWT_ALGORITHM)
    request = service_pb2.LogoutRequest(access_token=access_token)
    
    mock_redis_client, _ = patch_redis
    
    resp = await handle_logout(request)
    
    assert resp.success is True
    assert "Logged out successfully" in resp.message
    
    # Verify session deletion in Redis
    mock_redis_client.delete.assert_called_with(f"user_session:{user_id}")

@pytest.mark.asyncio
async def test_handle_logout_invalid_token():
    request = service_pb2.LogoutRequest(access_token="invalid_token")
    resp = await handle_logout(request)
    assert resp.success is False
    assert "Invalid token" in resp.message
