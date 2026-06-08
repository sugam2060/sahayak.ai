import asyncio
import json
import logging
from typing import Optional
from services.api_gateway.routers.presence.presence_manager import presence_manager

logger = logging.getLogger("api_gateway.presence.subscriber")

_subscriber_task: Optional[asyncio.Task] = None

async def subscribe_presence_updates():
    """
    Subscribes to Redis presence channel events and broadcasts them to WebSocket clients in same org.
    """
    from shared.redis_pool import RedisPool
    redis_client = RedisPool.get_client()
    
    pubsub = redis_client.pubsub()
    
    try:
        await pubsub.psubscribe("presence:*")
        logger.info("[Presence Subscriber] Successfully subscribed to 'presence:*' pub/sub updates.")
        
        async for message in pubsub.listen():
            if message["type"] == "pmessage":
                # We ignore messages from channel keys that don't match the standard prefix (e.g. keyevent expired notifications)
                channel = message["channel"]
                if not channel.startswith("presence:"):
                    continue
                # Ignore active set key (not a channel, but just in case)
                if ":org:" in channel:
                    continue
                try:
                    payload = json.loads(message["data"])
                    org_id = payload.get("orgId")
                    if org_id:
                        # Construct standard WebSocket event format
                        ws_event = {
                            "event": "presence:update",
                            "userId": payload.get("userId"),
                            "orgId": payload.get("orgId"),
                            "status": payload.get("status"),
                            "ts": payload.get("ts")
                        }
                        logger.info(f"[Presence Subscriber] Broadcasting presence update for user {payload.get('userId')} in org: {org_id}")
                        await presence_manager.broadcast(org_id, ws_event)
                except Exception as parse_err:
                    logger.warning(f"[Presence Subscriber] Failed to parse or broadcast message: {parse_err}")
    except asyncio.CancelledError:
        logger.info("[Presence Subscriber] Task cancelled.")
    except Exception as e:
        logger.error(f"[Presence Subscriber] Exception in presence subscriber: {e}", exc_info=True)
    finally:
        try:
            await pubsub.punsubscribe()
            await pubsub.close()
        except Exception:
            pass
        logger.info("[Presence Subscriber] PubSub connection closed.")

async def start_presence_subscriber():
    global _subscriber_task
    if _subscriber_task is None or _subscriber_task.done():
        _subscriber_task = asyncio.create_task(subscribe_presence_updates())
        logger.info("[Presence Subscriber] Background presence subscriber task started.")

async def stop_presence_subscriber():
    global _subscriber_task
    if _subscriber_task and not _subscriber_task.done():
        logger.info("[Presence Subscriber] Stopping background presence subscriber task...")
        _subscriber_task.cancel()
        try:
            await _subscriber_task
        except asyncio.CancelledError:
            pass
        _subscriber_task = None
