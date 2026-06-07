import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import status
from uuid import uuid4, UUID
from shared.database.schema import Team, TeamMember, User, UserRole
from shared.utils import get_db

@pytest.fixture
def override_db(test_client, mock_db_session):
    from shared.utils import get_db as route_get_db
    
    async def _get_db():
        yield mock_db_session
        
    test_client.app.dependency_overrides[route_get_db] = _get_db
    yield
    test_client.app.dependency_overrides.pop(route_get_db, None)

def test_get_teams_success(test_client, override_db, mock_db_session):
    test_client.cookies.set("access_token", "fake_access_token")
    
    org_id = uuid4()
    # Mocking database to return teams
    mock_team = Team(
        id=uuid4(),
        organization_id=org_id,
        team_name="Engineering Squad",
        description="Core Engineers",
        role="ENGINEER"
    )
    mock_team.members = []
    
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [mock_team]
    mock_db_session.execute.return_value = mock_result
    
    response = test_client.get("/api/teams")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert len(data) == 1
    assert data[0]["team_name"] == "Engineering Squad"
    assert data[0]["role"] == "ENGINEER"

def test_create_team_success(test_client, override_db, mock_db_session):
    test_client.cookies.set("access_token", "fake_access_token")
    
    org_id = uuid4()
    team_id = uuid4()
    mock_team = Team(
        id=team_id,
        organization_id=org_id,
        team_name="Billing Squad",
        description="Handles subscriptions",
        role="BILLING"
    )
    mock_team.members = []
    
    # Mock execute for checking details
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_team
    mock_db_session.execute.return_value = mock_result
    
    payload = {
        "team_name": "Billing Squad",
        "description": "Handles subscriptions",
        "role": "BILLING"
    }
    
    response = test_client.post("/api/teams", json=payload)
    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()
    assert data["team_name"] == "Billing Squad"
    assert data["role"] == "BILLING"

def test_create_team_forbidden(test_client, override_db, mock_auth_stub):
    # Set role to AGENT (lowercase or uppercase)
    mock_auth_stub.VerifyAccessToken.return_value = \
        mock_auth_stub.VerifyAccessToken.return_value.__class__(
            valid=True,
            message="Token is valid",
            user_id="22222222-3333-4444-5555-666666666666",
            organization_id="11111111-2222-3333-4444-555555555555",
            organization_name="Test Org",
            role="AGENT"
        )
    test_client.cookies.set("access_token", "fake_access_token")
    
    payload = {
        "team_name": "Agent Squad",
        "description": "Should fail",
        "role": "AGENT"
    }
    response = test_client.post("/api/teams", json=payload)
    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert "lacks the 'teams' permission" in response.json()["detail"]

def test_assign_team_member_success(test_client, override_db, mock_db_session):
    test_client.cookies.set("access_token", "fake_access_token")
    
    org_id = UUID("11111111-2222-3333-4444-555555555555")
    team_id = uuid4()
    user_id = uuid4()
    
    mock_team = Team(id=team_id, organization_id=org_id, team_name="Support", role="AGENT")
    mock_user = User(id=user_id, organization_id=org_id, email="agent@test.com", full_name="Agent Joe")
    
    # Mocking consecutive db fetches (team, user)
    mock_result_team = MagicMock()
    mock_result_team.scalar_one_or_none.return_value = mock_team
    
    mock_result_user = MagicMock()
    mock_result_user.scalar_one_or_none.return_value = mock_user
    
    mock_db_session.execute.side_effect = [mock_result_team, mock_result_user, MagicMock()]
    
    payload = {"user_id": str(user_id)}
    response = test_client.post(f"/api/teams/{team_id}/members", json=payload)
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["success"] is True

def test_remove_team_member_success(test_client, override_db, mock_db_session):
    test_client.cookies.set("access_token", "fake_access_token")
    
    org_id = UUID("11111111-2222-3333-4444-555555555555")
    team_id = uuid4()
    user_id = uuid4()
    
    mock_team = Team(id=team_id, organization_id=org_id, team_name="Support", role="AGENT")
    
    mock_result_team = MagicMock()
    mock_result_team.scalar_one_or_none.return_value = mock_team
    
    mock_result_del = MagicMock()
    mock_result_del.rowcount = 1
    
    mock_db_session.execute.side_effect = [mock_result_team, mock_result_del]
    
    response = test_client.delete(f"/api/teams/{team_id}/members/{user_id}")
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["success"] is True

@patch("services.api_gateway.routers.teams.members.KafkaProducerPool.send_message", new_callable=AsyncMock)
def test_invite_member_success(mock_send_kafka, test_client, override_db, mock_db_session, mock_redis_client):
    test_client.cookies.set("access_token", "fake_access_token")
    
    org_id = UUID("11111111-2222-3333-4444-555555555555")
    
    # Mock verify email not existing
    mock_res_exist = MagicMock()
    mock_res_exist.scalar_one_or_none.return_value = None
    
    mock_db_session.execute.return_value = mock_res_exist
    
    payload = {
        "full_name": "Invited Agent",
        "email": "invited@example.com",
        "password": "temporary_pass",
        "role": "AGENT"
    }
    
    # Mock verification template read
    with patch("builtins.open", mock_open_verification_template()):
        response = test_client.post("/api/teams/invite", json=payload)
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["success"] is True
        assert mock_send_kafka.called

def mock_open_verification_template():
    from unittest.mock import mock_open
    m = mock_open(read_data="<html>{{full_name}} - {{verify_link}}</html>")
    return m

def test_teams_permission_success_for_non_owner(test_client, override_db, mock_db_session, mock_auth_stub):
    mock_auth_stub.VerifyAccessToken.return_value = \
        mock_auth_stub.VerifyAccessToken.return_value.__class__(
            valid=True,
            message="Token is valid",
            user_id="22222222-3333-4444-5555-666666666666",
            organization_id="11111111-2222-3333-4444-555555555555",
            organization_name="Test Org",
            role="ADMIN"
        )
    test_client.cookies.set("access_token", "fake_access_token")

    # Mock DB query for permissions: returns ['teams']
    mock_execute_res_permissions = MagicMock()
    mock_execute_res_permissions.scalar_one_or_none.return_value = ["teams"]

    # Mock DB query for teams list: returns a mock team
    mock_team = Team(
        id=uuid4(),
        organization_id=UUID("11111111-2222-3333-4444-555555555555"),
        team_name="Engineering Squad",
        description="Core Engineers",
        role="ENGINEER"
    )
    mock_team.members = []
    mock_execute_res_teams = MagicMock()
    mock_execute_res_teams.scalars.return_value.all.return_value = [mock_team]

    # Set mock db execution return side effect (permissions check query first, then get teams query)
    mock_db_session.execute.side_effect = [mock_execute_res_permissions, mock_execute_res_teams]

    response = test_client.get("/api/teams")
    assert response.status_code == status.HTTP_200_OK
    assert len(response.json()) == 1

def test_teams_permission_forbidden_for_non_owner(test_client, override_db, mock_db_session, mock_auth_stub):
    mock_auth_stub.VerifyAccessToken.return_value = \
        mock_auth_stub.VerifyAccessToken.return_value.__class__(
            valid=True,
            message="Token is valid",
            user_id="22222222-3333-4444-5555-666666666666",
            organization_id="11111111-2222-3333-4444-555555555555",
            organization_name="Test Org",
            role="ADMIN"
        )
    test_client.cookies.set("access_token", "fake_access_token")

    # Mock DB query for permissions: returns empty permissions
    mock_execute_res_permissions = MagicMock()
    mock_execute_res_permissions.scalar_one_or_none.return_value = []

    mock_db_session.execute.return_value = mock_execute_res_permissions

    response = test_client.get("/api/teams")
    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert "Your team lacks the 'teams' permission" in response.json()["detail"]
