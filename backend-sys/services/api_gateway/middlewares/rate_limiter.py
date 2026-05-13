import time
import redis.asyncio as redis
from fastapi import Request, HTTPException, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from shared.config import REDIS_URL

class SlidingWindowRateLimiter(BaseHTTPMiddleware):
    def __init__(self, app, window_size: int = 60, max_requests: int = 10, include_paths: list[str] = None, exclude_paths: list[str] = None):
        super().__init__(app)
        self.window_size = window_size
        self.max_requests = max_requests
        self.include_paths = include_paths
        self.exclude_paths = exclude_paths
        # Initialize Redis connection
        kwargs = {"decode_responses": True}
        if REDIS_URL.startswith("rediss://"):
            kwargs["ssl_cert_reqs"] = "none"
        self.redis = redis.from_url(REDIS_URL, **kwargs)

    async def dispatch(self, request: Request, call_next):
        # Skip rate limiting if path is explicitly excluded
        if self.exclude_paths is not None:
            if any(request.url.path.startswith(path) for path in self.exclude_paths):
                return await call_next(request)

        # Skip rate limiting if path is not in include_paths
        if self.include_paths is not None:
            if not any(request.url.path.startswith(path) for path in self.include_paths):
                return await call_next(request)

        client_ip = request.client.host
        now = time.time()
        
        current_window_start = int(now // self.window_size) * self.window_size
        prev_window_start = current_window_start - self.window_size

        # Keys for current and previous windows
        curr_key = f"rate_limit:{client_ip}:{current_window_start}"
        prev_key = f"rate_limit:{client_ip}:{prev_window_start}"

        # Fetch counts from Redis in a pipeline
        async with self.redis.pipeline(transaction=True) as pipe:
            pipe.get(curr_key)
            pipe.get(prev_key)
            results = await pipe.execute()
        
        curr_count = int(results[0]) if results[0] else 0
        prev_count = int(results[1]) if results[1] else 0

        # Calculate weighted count
        fraction = (now - current_window_start) / self.window_size
        weighted_count = prev_count * (1 - fraction) + curr_count

        if weighted_count >= self.max_requests:
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={"detail": "Too many requests. Please try again later."}
            )

        # Increment current window count and set TTL (window_size * 2 to cover prev/curr usage)
        async with self.redis.pipeline(transaction=True) as pipe:
            pipe.incr(curr_key)
            pipe.expire(curr_key, self.window_size * 2)
            await pipe.execute()

        response = await call_next(request)
        return response
