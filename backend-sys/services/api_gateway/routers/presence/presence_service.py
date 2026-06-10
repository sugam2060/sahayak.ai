import json
import time
from typing import Optional, List, Dict, Any
import logging

logger = logging.getLogger("api_gateway.presence.service")

class PresenceService:
    def __init__(self, redis_client=None):
        from shared.redis_pool import RedisPool
        self.redis = redis_client or RedisPool.get_client()
        self.hash_ttl = 30  # seconds

    def hash_key(self, org_id: str, user_id: str) -> str:
        return f"presence:{org_id}:{user_id}"

    def active_set_key(self, org_id: str) -> str:
        return f"presence:org:{org_id}:active"

    def sockets_key(self, user_id: str) -> str:
        return f"presence:user:{user_id}:sockets"

    def channel_key(self, org_id: str) -> str:
        return f"presence:{org_id}"

    async def set_online(
        self,
        org_id: str,
        user_id: str,
        socket_id: str,
        device_type: str = "web",
        status: str = "online",
        active_tab: str = "",
        meta: Optional[Dict[str, Any]] = None
    ) -> None:
        now_ms = int(time.time() * 1000)
        hkey = self.hash_key(org_id, user_id)
        skey = self.sockets_key(user_id)
        akey = self.active_set_key(org_id)

        meta_json = json.dumps(meta or {})
        
        async with self.redis.pipeline(transaction=True) as pipe:
            pipe.hset(hkey, mapping={
                "status": status,
                "lastSeen": str(now_ms),
                "socketId": socket_id,
                "deviceType": device_type,
                "activeTab": active_tab,
                "meta": meta_json
            })
            pipe.expire(hkey, self.hash_ttl)
            pipe.zadd(akey, {user_id: now_ms})
            pipe.sadd(skey, socket_id)
            await pipe.execute()
        
        await self.publish(org_id, user_id, status)

    async def heartbeat(self, org_id: str, user_id: str, socket_id: str) -> None:
        now_ms = int(time.time() * 1000)
        hkey = self.hash_key(org_id, user_id)
        akey = self.active_set_key(org_id)

        # Check if user status hash still exists to avoid resurrecting deleted user
        exists = await self.redis.exists(hkey)
        if not exists:
            logger.warning(f"Heartbeat received for non-existent presence key: {hkey}")
            return

        async with self.redis.pipeline(transaction=True) as pipe:
            pipe.hset(hkey, "lastSeen", str(now_ms))
            pipe.expire(hkey, self.hash_ttl)
            pipe.zadd(akey, {user_id: now_ms})
            await pipe.execute()

    async def set_status(self, org_id: str, user_id: str, status: str) -> None:
        hkey = self.hash_key(org_id, user_id)
        exists = await self.redis.exists(hkey)
        if not exists:
            return
        
        await self.redis.hset(hkey, "status", status)
        await self.publish(org_id, user_id, status)

    async def set_offline(self, org_id: str, user_id: str, socket_id: str) -> None:
        skey = self.sockets_key(user_id)
        await self.redis.srem(skey, socket_id)
        
        remaining = await self.redis.scard(skey)
        if remaining > 0:
            return  # still connected via another device/tab
        
        hkey = self.hash_key(org_id, user_id)
        akey = self.active_set_key(org_id)
        
        async with self.redis.pipeline(transaction=True) as pipe:
            pipe.delete(hkey)
            pipe.zrem(akey, user_id)
            await pipe.execute()
            
        await self.publish(org_id, user_id, "offline")

    async def handle_expired_key(self, org_id: str, user_id: str) -> None:
        akey = self.active_set_key(org_id)
        skey = self.sockets_key(user_id)
        
        async with self.redis.pipeline(transaction=True) as pipe:
            pipe.zrem(akey, user_id)
            pipe.delete(skey)
            await pipe.execute()
            
        await self.publish(org_id, user_id, "offline")

    async def get_status(self, org_id: str, user_id: str) -> Optional[Dict[str, Any]]:
        hkey = self.hash_key(org_id, user_id)
        raw = await self.redis.hgetall(hkey)
        if not raw or "status" not in raw:
            return None
        return {
            "status": raw.get("status"),
            "lastSeen": int(raw.get("lastSeen", 0)),
            "socketId": raw.get("socketId"),
            "deviceType": raw.get("deviceType"),
            "activeTab": raw.get("activeTab"),
            "meta": json.loads(raw.get("meta", "{}"))
        }

    async def get_org_online_users(self, org_id: str, within_seconds: int = 300) -> List[str]:
        akey = self.active_set_key(org_id)
        since = int((time.time() - within_seconds) * 1000)
        return await self.redis.zrangebyscore(akey, since, "+inf")

    async def get_bulk_status(self, org_id: str, user_ids: List[str]) -> Dict[str, Optional[Dict[str, Any]]]:
        async with self.redis.pipeline(transaction=False) as pipe:
            for uid in user_ids:
                pipe.hgetall(self.hash_key(org_id, uid))
            results = await pipe.execute()
            
        out = {}
        for uid, raw in zip(user_ids, results):
            if not raw or "status" not in raw:
                out[uid] = None
            else:
                out[uid] = {
                    "status": raw.get("status"),
                    "lastSeen": int(raw.get("lastSeen", 0)),
                    "socketId": raw.get("socketId"),
                    "deviceType": raw.get("deviceType"),
                    "activeTab": raw.get("activeTab"),
                    "meta": json.loads(raw.get("meta", "{}"))
                }
        return out

    async def publish(self, org_id: str, user_id: str, status: str) -> None:
        event = {
            "userId": user_id,
            "orgId": org_id,
            "status": status,
            "ts": int(time.time() * 1000)
        }
        channel = self.channel_key(org_id)
        await self.redis.publish(channel, json.dumps(event))

        if status == "offline":
            try:
                import asyncio
                from services.api_gateway.routers.chat_routers.handoff_service import handle_user_offline
                asyncio.create_task(handle_user_offline(org_id, user_id))
            except Exception as e:
                logger.error(f"Failed to trigger handoff check on user offline: {e}")
