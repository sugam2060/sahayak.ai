import pytest
from unittest.mock import AsyncMock, MagicMock
from fastapi import status

def test_rate_limiter_allows_options_requests(test_client, mock_redis_client):
    # Force building the middleware stack if it hasn't been built yet
    if test_client.app.middleware_stack is None:
        test_client.app.middleware_stack = test_client.app.build_middleware_stack()

    # Find the SlidingWindowRateLimiter instance in the FastAPI middleware stack
    rate_limiter_instance = None
    curr = test_client.app.middleware_stack
    while curr is not None:
        if curr.__class__.__name__ == "SlidingWindowRateLimiter":
            rate_limiter_instance = curr
            break
        curr = getattr(curr, "app", None)

    assert rate_limiter_instance is not None, "Could not find SlidingWindowRateLimiter in middleware stack"
    
    # Configure the actual rate limiter's redis mock
    mock_pipe = AsyncMock()
    mock_pipe.get = MagicMock()
    mock_pipe.incr = MagicMock()
    mock_pipe.expire = MagicMock()
    mock_pipe.execute = AsyncMock(return_value=[15, 0])
    
    rate_limiter_instance.redis.pipeline = MagicMock(
        return_value=AsyncMock(__aenter__=AsyncMock(return_value=mock_pipe))
    )
    
    # Send a POST request, which should be rate limited (429)
    payload = {
        "org_name": "My Org",
        "org_slug": "my-org",
        "full_name": "John Doe",
        "email": "john@example.com",
        "password": "securepassword"
    }
    response_post = test_client.post("/auth/register", json=payload)
    assert response_post.status_code == status.HTTP_429_TOO_MANY_REQUESTS
    assert response_post.json()["detail"] == "Too many requests. Please try again later."
    
    # Send an OPTIONS request (CORS preflight request), which should NOT be rate limited
    response_options = test_client.options(
        "/auth/register",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "Content-Type",
        }
    )
    # CORSMiddleware should handle the OPTIONS request and return OK (usually 200)
    assert response_options.status_code == status.HTTP_200_OK
