import time
import redis.asyncio as redis
from shared.config import REDIS_URL

class SlidingWindowRateLimiter:
    def __init__(self, app, window_size: int = 60, max_requests: int = 10, include_paths: list[str] = None, exclude_paths: list[str] = None):
        self.app = app
        self.window_size = window_size
        self.max_requests = max_requests
        self.include_paths = include_paths
        self.exclude_paths = exclude_paths
        # Initialize Redis connection
        kwargs = {"decode_responses": True}
        if REDIS_URL.startswith("rediss://"):
            kwargs["ssl_cert_reqs"] = "none"
        self.redis = redis.from_url(REDIS_URL, **kwargs)

    async def __call__(self, scope, receive, send):
        # By-pass rate limiting for non-HTTP scopes (like WebSockets and Lifespan)
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")
        method = scope.get("method", "")

        # Skip rate limiting for preflight (OPTIONS) requests
        if method == "OPTIONS":
            await self.app(scope, receive, send)
            return

        # Skip rate limiting if path is explicitly excluded
        if self.exclude_paths is not None:
            if any(path.startswith(p) for p in self.exclude_paths):
                await self.app(scope, receive, send)
                return

        # Skip rate limiting if path is not in include_paths
        if self.include_paths is not None:
            if not any(path.startswith(p) for p in self.include_paths):
                await self.app(scope, receive, send)
                return

        # Get client IP from scope
        client = scope.get("client")
        client_ip = client[0] if client else "unknown"
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
            # Send HTTP 429 response via ASGI
            response_body = b'{"detail": "Too many requests. Please try again later."}'
            await send({
                "type": "http.response.start",
                "status": 429,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"content-length", str(len(response_body)).encode("utf-8")),
                ]
            })
            await send({
                "type": "http.response.body",
                "body": response_body,
                "more_body": False
            })
            return

        # Increment current window count and set TTL (window_size * 2 to cover prev/curr usage)
        async with self.redis.pipeline(transaction=True) as pipe:
            pipe.incr(curr_key)
            pipe.expire(curr_key, self.window_size * 2)
            await pipe.execute()

        await self.app(scope, receive, send)
