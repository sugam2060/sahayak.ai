import asyncio
import logging
import re
from typing import Optional
from services.api_gateway.routers.presence.presence_service import PresenceService

logger = logging.getLogger("api_gateway.presence.listener")

_listener_task: Optional[asyncio.Task] = None

async def listen_expired_keys():
    """
    Subscribes to Redis expired keyspace events and handles presence status timeouts.
    """
    from shared.redis_pool import RedisPool
    redis_client = RedisPool.get_client()
    presence_service = PresenceService(redis_client)
    
    # Try to configure keyspace notifications
    try:
        await redis_client.config_set("notify-keyspace-events", "Ex")
        logger.info("[Presence Listener] Enabled Redis keyspace notifications (Ex).")
    except Exception as e:
        logger.warning(f"[Presence Listener] Could not run CONFIG SET notify-keyspace-events Ex: {e}. "
                       "Ensure keyspace notifications are enabled manually on the Redis server.")

    # We use pubsub pattern to match expired key events on any database index (e.g. database 0)
    pubsub = redis_client.pubsub()
    
    try:
        await pubsub.psubscribe("__keyevent@*__:expired")
        logger.info("[Presence Listener] Successfully subscribed to __keyevent@*__:expired.")
        
        async for message in pubsub.listen():
            if message["type"] == "pmessage":
                key = message["data"]
                # Match pattern: presence:{orgId}:{userId}
                # Use regex to parse orgId and userId
                match = re.match(r"^presence:([^:]+):(.+)$", key)
                if match:
                    org_id, user_id = match.groups()
                    logger.info(f"[Presence Listener] Detected presence key expiry: {key}. Marking user offline.")
                    try:
                        await presence_service.handle_expired_key(org_id, user_id)
                    except Exception as err:
                        logger.error(f"[Presence Listener] Error handling key expiry for user {user_id}: {err}")
    except asyncio.CancelledError:
        logger.info("[Presence Listener] Task cancelled.")
    except Exception as e:
        logger.error(f"[Presence Listener] Exception in keyspace listener: {e}", exc_info=True)
    finally:
        try:
            await pubsub.punsubscribe()
            await pubsub.close()
        except Exception:
            pass
        logger.info("[Presence Listener] PubSub connection closed.")

async def start_presence_listener():
    global _listener_task
    if _listener_task is None or _listener_task.done():
        _listener_task = asyncio.create_task(listen_expired_keys())
        logger.info("[Presence Listener] Background keyspace listener task started.")

async def stop_presence_listener():
    global _listener_task
    if _listener_task and not _listener_task.done():
        logger.info("[Presence Listener] Stopping background keyspace listener task...")
        _listener_task.cancel()
        try:
            await _listener_task
        except asyncio.CancelledError:
            pass
        _listener_task = None
