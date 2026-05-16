import redis.asyncio as redis
from shared.config import REDIS_URL

class RedisPool:
    _client = None

    @classmethod
    def get_client(cls):
        if cls._client is None:
            redis_kwargs = {
                "decode_responses": True,
                "max_connections": 50,
                "socket_timeout": 5.0,
                "socket_connect_timeout": 5.0,
                "retry_on_timeout": True
            }
            if REDIS_URL.startswith("rediss://"):
                redis_kwargs["ssl_cert_reqs"] = "none"
            cls._client = redis.from_url(REDIS_URL, **redis_kwargs)
        return cls._client

    @classmethod
    async def close(cls):
        if cls._client:
            await cls._client.close()
            cls._client = None
