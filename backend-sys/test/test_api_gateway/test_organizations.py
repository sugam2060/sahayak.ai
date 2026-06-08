import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import status
from uuid import uuid4, UUID
from datetime import datetime
from shared.database.schema import Organization, User, UserRole
from shared.database.schema.organizations import PlanType
from shared.utils import get_db

@pytest.fixture
def override_db(test_client, mock_db_session):
    from shared.utils import get_db as route_get_db
    
    async def _get_db():
        yield mock_db_session
        
    test_client.app.dependency_overrides[route_get_db] = _get_db
    yield
    test_client.app.dependency_overrides.pop(route_get_db, None)

def test_get_organization_success(test_client, override_db, mock_db_session):
    test_client.cookies.set("access_token", "fake_access_token")
    
    org_id = uuid4()
    mock_org = Organization(
        id=org_id,
        name="Sahayak Devs",
        slug="sahayak-devs",
        is_active=True,
        plan=PlanType.FREE,
        created_at=datetime.now(),
        updated_at=datetime.now()
    )
    
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_org
    mock_db_session.execute.return_value = mock_result
    
    response = test_client.get("/api/organizations/current")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["name"] == "Sahayak Devs"
    assert data["slug"] == "sahayak-devs"
    assert data["is_active"] is True

def test_get_organization_forbidden(test_client, override_db, mock_auth_stub):
    test_client.cookies.set("access_token", "fake_access_token")
    
    # Force mock_auth_stub to return AGENT (which does not have org_settings permission by default)
    mock_auth_stub.VerifyAccessToken.return_value = \
        mock_auth_stub.VerifyAccessToken.return_value.__class__(
            valid=True,
            message="Token is valid",
            role="AGENT",
            user_id="22222222-3333-4444-5555-666666666666",
            organization_id="11111111-2222-3333-4444-555555555555"
        )
        
    response = test_client.get("/api/organizations/current")
    assert response.status_code == status.HTTP_403_FORBIDDEN

def test_update_organization_success(test_client, override_db, mock_db_session):
    test_client.cookies.set("access_token", "fake_access_token")
    
    org_id = uuid4()
    mock_org = Organization(
        id=org_id,
        name="Old Name",
        slug="old-name",
        is_active=True,
        plan=PlanType.FREE,
        created_at=datetime.now(),
        updated_at=datetime.now()
    )
    
    # 1. Mocking get_organization
    # 2. Mocking slug uniqueness check (returns None => unique)
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.side_effect = [mock_org, None]
    mock_db_session.execute.return_value = mock_result
    
    payload = {
        "name": "New Name",
        "slug": "new-name"
    }
    
    response = test_client.put("/api/organizations/current", json=payload)
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["name"] == "New Name"
    assert data["slug"] == "new-name"

def test_update_organization_duplicate_slug(test_client, override_db, mock_db_session):
    test_client.cookies.set("access_token", "fake_access_token")
    
    org_id = uuid4()
    mock_org = Organization(
        id=org_id,
        name="Old Name",
        slug="old-name",
        is_active=True,
        plan=PlanType.FREE,
        created_at=datetime.now(),
        updated_at=datetime.now()
    )
    
    # Return mock_org for get_organization, but return ANOTHER org for slug check
    another_org = Organization(
        id=uuid4(),
        name="Conflict",
        slug="conflict-slug",
        plan=PlanType.FREE,
        created_at=datetime.now(),
        updated_at=datetime.now()
    )
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.side_effect = [mock_org, another_org]
    mock_db_session.execute.return_value = mock_result
    
    payload = {
        "slug": "conflict-slug"
    }
    
    response = test_client.put("/api/organizations/current", json=payload)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "slug is already taken" in response.json()["detail"].lower()

def test_deactivate_organization_success(test_client, override_db, mock_db_session, mock_redis_client):
    test_client.cookies.set("access_token", "fake_access_token")
    
    org_id = uuid4()
    mock_org = Organization(
        id=org_id,
        name="Active Org",
        slug="active-org",
        is_active=True,
        plan=PlanType.FREE,
        created_at=datetime.now(),
        updated_at=datetime.now()
    )
    
    # Get organization first, then get users in organization
    mock_user = User(
        id=uuid4(),
        email="test@user.com",
        is_active=True,
        organization_id=org_id
    )
    
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_org
    mock_result.scalars.return_value.all.return_value = [mock_user]
    mock_db_session.execute.return_value = mock_result
    
    # Mock Redis delete
    mock_redis_client.delete = AsyncMock(return_value=2)
    
    response = test_client.delete("/api/organizations/current")
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["success"] is True
    assert mock_org.is_active is False
    
    # Assert Redis session key deleted
    mock_redis_client.delete.assert_called_once()
    args = mock_redis_client.delete.call_args[0]
    assert f"user_session:{mock_user.id}" in args
    assert f"user_auth_cache:{mock_user.email}" in args
