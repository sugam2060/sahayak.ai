import pytest
import grpc
from unittest.mock import AsyncMock
from fastapi import status
from shared.proto import service_pb2

def test_register_success(test_client, mock_auth_stub):
    payload = {
        "org_name": "My Org",
        "org_slug": "my-org",
        "full_name": "John Doe",
        "email": "john@example.com",
        "password": "securepassword"
    }
    response = test_client.post("/auth/register", json=payload)
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["organization_id"] == "11111111-2222-3333-4444-555555555555"
    assert data["user_id"] == "22222222-3333-4444-5555-666666666666"
    assert data["message"] == "Registration successful"

def test_register_already_exists(test_client, mock_auth_stub):
    # Mock gRPC error
    aio_error = grpc.aio.AioRpcError(
        code=grpc.StatusCode.ALREADY_EXISTS,
        initial_metadata=None,
        trailing_metadata=None,
        details="Email already registered",
        debug_error_string=None
    )
    mock_auth_stub.Register.side_effect = aio_error
    
    payload = {
        "org_name": "My Org",
        "org_slug": "my-org",
        "full_name": "John Doe",
        "email": "john@example.com",
        "password": "securepassword"
    }
    response = test_client.post("/auth/register", json=payload)
    assert response.status_code == status.HTTP_409_CONFLICT
    assert response.json()["detail"] == "Email already registered"
    mock_auth_stub.Register.side_effect = None  # Reset side effect

def test_login_success(test_client, mock_auth_stub):
    payload = {
        "email": "test@example.com",
        "password": "password123"
    }
    response = test_client.post("/auth/login", json=payload)
    assert response.status_code == status.HTTP_200_OK
    assert response.cookies.get("access_token") == "fake_access_token"
    assert response.cookies.get("refresh_token") == "fake_refresh_token"
    data = response.json()
    assert data["success"] is True
    assert data["email"] == "test@example.com"

def test_login_unverified_email(test_client, mock_auth_stub):
    mock_auth_stub.Login.return_value = service_pb2.LoginResponse(
        success=False,
        message="Please verify your email."
    )
    payload = {
        "email": "test@example.com",
        "password": "password123"
    }
    response = test_client.post("/auth/login", json=payload)
    # The endpoint catches "verify your email" and returns success=False with 200 OK
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["success"] is False
    assert data["is_verified"] is False
    assert "verify" in data["message"].lower()

def test_login_failure(test_client, mock_auth_stub):
    mock_auth_stub.Login.return_value = service_pb2.LoginResponse(
        success=False,
        message="Invalid email or password."
    )
    payload = {
        "email": "test@example.com",
        "password": "password123"
    }
    response = test_client.post("/auth/login", json=payload)
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert response.json()["detail"] == "Invalid email or password."

def test_verify_email_success(test_client, mock_auth_stub):
    response = test_client.get("/auth/verify/some-token-123")
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["success"] is True
    assert response.json()["message"] == "Email verified successfully"

def test_verify_email_failure(test_client, mock_auth_stub):
    mock_auth_stub.VerifyEmail.return_value = service_pb2.VerifyEmailResponse(
        success=False,
        message="Invalid token"
    )
    response = test_client.get("/auth/verify/some-token-123")
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.json()["detail"] == "Invalid token"

def test_read_users_me_success(test_client, mock_auth_stub):
    test_client.cookies.set("access_token", "fake_access_token")
    response = test_client.get("/auth/me")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["success"] is True
    assert data["user"]["user_id"] == "22222222-3333-4444-5555-666666666666"
    assert data["user"]["organization_name"] == "Test Org"

def test_read_users_me_missing_token_with_refresh(test_client, mock_auth_stub):
    test_client.cookies.set("refresh_token", "fake_refresh_token")
    # Redirect check is returned as 307 Temporary Redirect
    response = test_client.get("/auth/me", follow_redirects=False)
    assert response.status_code == status.HTTP_307_TEMPORARY_REDIRECT
    assert "/auth/refresh_token" in response.headers["location"]

def test_read_users_me_missing_all_tokens(test_client, mock_auth_stub):
    response = test_client.get("/auth/me")
    assert response.status_code == status.HTTP_401_UNAUTHORIZED

def test_refresh_token_success(test_client, mock_auth_stub):
    test_client.cookies.set("refresh_token", "fake_refresh_token")
    response = test_client.post("/auth/refresh_token")
    assert response.status_code == status.HTTP_200_OK
    assert response.cookies.get("access_token") == "fake_new_access_token"
    assert response.cookies.get("refresh_token") == "fake_new_refresh_token"
    assert response.json()["success"] is True

def test_refresh_token_missing(test_client, mock_auth_stub):
    response = test_client.post("/auth/refresh_token")
    assert response.status_code == status.HTTP_401_UNAUTHORIZED

def test_logout(test_client, mock_auth_stub):
    test_client.cookies.set("access_token", "fake_access_token")
    response = test_client.post("/auth/logout")
    assert response.status_code == status.HTTP_200_OK
    assert not response.cookies.get("access_token")
    assert not response.cookies.get("refresh_token")
    assert response.json()["success"] is True
    mock_auth_stub.Logout.assert_called_once()
