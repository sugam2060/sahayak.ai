import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import status
from uuid import uuid4, UUID
from datetime import datetime

from shared.database.schema.users import User, UserRole
from shared.utils import get_db


@pytest.fixture
def override_db(test_client, mock_db_session):
    from shared.utils import get_db as route_get_db

    async def _get_db():
        yield mock_db_session

    test_client.app.dependency_overrides[route_get_db] = _get_db
    yield
    test_client.app.dependency_overrides.pop(route_get_db, None)


def _make_mock_user():
    """Return a lightweight mock User object matching the DB schema."""
    mock_user = MagicMock(spec=User)
    mock_user.id = UUID("22222222-3333-4444-5555-666666666666")
    mock_user.full_name = "Test User"
    mock_user.email = "test@example.com"
    mock_user.role = UserRole.OWNER
    mock_user.password_hash = "hashed_correct_password"
    mock_user.created_at = datetime(2026, 1, 1)
    mock_user.last_login_at = datetime(2026, 6, 1)
    return mock_user


# ------------------------------------------------------------------ #
# GET /api/account/profile                                              #
# ------------------------------------------------------------------ #
def test_get_profile_success(test_client, override_db, mock_db_session):
    """OWNER should receive a 200 with their account profile."""
    test_client.cookies.set("access_token", "fake_access_token")

    mock_user = _make_mock_user()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_user
    mock_db_session.execute = AsyncMock(return_value=mock_result)

    response = test_client.get("/api/account/profile")
    assert response.status_code == status.HTTP_200_OK

    data = response.json()
    assert data["full_name"] == "Test User"
    assert data["email"] == "test@example.com"
    assert data["role"] == "OWNER"


def test_get_profile_no_auth(test_client, override_db):
    """Unauthenticated request should receive 401."""
    response = test_client.get("/api/account/profile")
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


# ------------------------------------------------------------------ #
# PATCH /api/account/name                                               #
# ------------------------------------------------------------------ #
def test_update_name_success(test_client, override_db, mock_db_session):
    """Should update name and return 200."""
    test_client.cookies.set("access_token", "fake_access_token")

    mock_db_session.begin = MagicMock(return_value=AsyncMock(
        __aenter__=AsyncMock(return_value=None),
        __aexit__=AsyncMock(return_value=False),
    ))
    mock_result = MagicMock()
    mock_db_session.execute = AsyncMock(return_value=mock_result)

    with patch("services.api_gateway.routers.account.crud.AccountService._invalidate_session", new=AsyncMock()):
        response = test_client.patch(
            "/api/account/name",
            json={"full_name": "Updated Name"},
        )

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["success"] is True


def test_update_name_too_short(test_client, override_db):
    """Name shorter than 2 characters should return 422."""
    test_client.cookies.set("access_token", "fake_access_token")

    response = test_client.patch("/api/account/name", json={"full_name": "A"})
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


# ------------------------------------------------------------------ #
# PATCH /api/account/password                                           #
# ------------------------------------------------------------------ #
def test_update_password_wrong_current(test_client, override_db, mock_db_session):
    """Wrong current password should return 400."""
    test_client.cookies.set("access_token", "fake_access_token")

    # Simulate DB returning the user's hash
    hash_result = MagicMock()
    hash_result.one_or_none.return_value = ("hashed_password",)
    mock_db_session.execute = AsyncMock(return_value=hash_result)

    with patch(
        "services.api_gateway.routers.account.crud.verify_password",
        return_value=False,
    ):
        response = test_client.patch(
            "/api/account/password",
            json={
                "current_password": "wrong",
                "new_password": "NewPass123!",
                "confirm_password": "NewPass123!",
            },
        )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "incorrect" in response.json()["detail"].lower()


def test_update_password_success(test_client, override_db, mock_db_session):
    """Correct current password should update and return 200."""
    test_client.cookies.set("access_token", "fake_access_token")

    hash_result = MagicMock()
    hash_result.one_or_none.return_value = ("hashed_correct_password",)
    mock_db_session.execute = AsyncMock(return_value=hash_result)
    mock_db_session.begin = MagicMock(return_value=AsyncMock(
        __aenter__=AsyncMock(return_value=None),
        __aexit__=AsyncMock(return_value=False),
    ))

    with patch(
        "services.api_gateway.routers.account.crud.verify_password",
        return_value=True,
    ), patch(
        "services.api_gateway.routers.account.crud.hash_password",
        return_value="new_hashed_password",
    ), patch(
        "services.api_gateway.routers.account.crud.AccountService._invalidate_session",
        new=AsyncMock(),
    ):
        response = test_client.patch(
            "/api/account/password",
            json={
                "current_password": "CorrectPass1",
                "new_password": "NewPass123!",
                "confirm_password": "NewPass123!",
            },
        )

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["success"] is True


def test_update_password_mismatch(test_client, override_db):
    """Mismatched new password and confirm should return 422."""
    test_client.cookies.set("access_token", "fake_access_token")

    response = test_client.patch(
        "/api/account/password",
        json={
            "current_password": "CorrectPass1",
            "new_password": "NewPass123!",
            "confirm_password": "DifferentPass!",
        },
    )
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


# ------------------------------------------------------------------ #
# POST /api/account/email/request-change                                #
# ------------------------------------------------------------------ #
def test_request_email_change_success(test_client, override_db, mock_db_session):
    """Should send email and return 200 when new email is unique."""
    test_client.cookies.set("access_token", "fake_access_token")

    mock_user = _make_mock_user()

    # First execute: profile lookup → user found
    profile_result = MagicMock()
    profile_result.scalar_one_or_none.return_value = mock_user

    # Second execute: uniqueness check → no existing user with new email
    uniqueness_result = MagicMock()
    uniqueness_result.scalar_one_or_none.return_value = None

    mock_db_session.execute = AsyncMock(
        side_effect=[profile_result, uniqueness_result]
    )

    with patch(
        "services.api_gateway.routers.account.crud.RedisPool.get_client"
    ) as mock_redis_factory, patch(
        "services.api_gateway.routers.account.crud.KafkaProducerPool.send_message",
        new=AsyncMock(),
    ), patch(
        "builtins.open",
        MagicMock(
            return_value=MagicMock(
                __enter__=MagicMock(return_value=MagicMock(read=MagicMock(return_value="Hello {{full_name}} {{new_email}} {{verify_link}}"))),
                __exit__=MagicMock(return_value=False),
            )
        ),
    ):
        mock_redis = AsyncMock()
        mock_redis.setex = AsyncMock(return_value=True)
        mock_redis_factory.return_value = mock_redis

        response = test_client.post(
            "/api/account/email/request-change",
            json={"new_email": "newaddress@example.com"},
        )

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["success"] is True


# ------------------------------------------------------------------ #
# POST /api/account/email/confirm/{token}                               #
# ------------------------------------------------------------------ #
def test_confirm_email_change_success(test_client, override_db, mock_db_session):
    """Should update email and return success message JSON."""
    mock_db_session.begin = MagicMock(return_value=AsyncMock(
        __aenter__=AsyncMock(return_value=None),
        __aexit__=AsyncMock(return_value=False),
    ))
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = "oldemail@example.com"
    mock_db_session.execute = AsyncMock(return_value=mock_result)

    with patch(
        "services.api_gateway.routers.account.crud.RedisPool.get_client"
    ) as mock_redis_factory:
        mock_redis = AsyncMock()
        # Redis stores "user_id:new_email"
        mock_redis.get = AsyncMock(return_value=b"22222222-3333-4444-5555-666666666666:newemail@example.com")
        mock_redis.delete = AsyncMock()
        mock_redis_factory.return_value = mock_redis

        response = test_client.post(
            "/api/account/email/confirm/valid_token",
        )

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["success"] is True
    assert "verified" in response.json()["message"].lower()


def test_confirm_email_change_invalid_token(test_client, override_db, mock_db_session):
    """Invalid token should return 400 Bad Request."""
    with patch(
        "services.api_gateway.routers.account.crud.RedisPool.get_client"
    ) as mock_redis_factory:
        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=None)
        mock_redis_factory.return_value = mock_redis

        response = test_client.post(
            "/api/account/email/confirm/invalid_token",
        )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "invalid" in response.json()["detail"].lower()
