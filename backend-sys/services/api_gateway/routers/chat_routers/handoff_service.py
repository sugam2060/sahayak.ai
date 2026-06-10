"""
Chat Handoff Service
Manages the peer-to-peer handoff flow between team members for customer conversations.
"""
import asyncio
import json
import logging
from datetime import datetime, timezone
from uuid import uuid4

from shared.database.mongodb import MongoDBManager
from shared.database.schema.internal_chat_mongo import HandoffRequestDetail, InternalMessageDetail
from shared.kafka_producer import KafkaProducerPool
from shared.redis_pool import RedisPool

logger = logging.getLogger("api_gateway.handoff_service")

# Handoff request expiry in seconds
HANDOFF_EXPIRY_SECONDS = 120

# Redis key patterns for chat locks
LOCK_KEY_PREFIX = "lock:chat"
LOCK_ORG_INDEX_PREFIX = "lock:org"
LOCK_SOCKET_PREFIX = "lock:socket"
LOCK_TTL_SECONDS = 7200  # 2 hours safety TTL


class ChatLockManager:
    """
    Manages Redis-backed chat locks.
    Key structure:
      - lock:chat:{org_id}:{conversation_id} -> JSON {user_id, socket_id, user_name, locked_at}
      - lock:org:{org_id}:active -> SET of conversation_ids
      - lock:socket:{socket_id} -> SET of "org_id:conversation_id" strings
    """

    @staticmethod
    async def acquire_lock(
        org_id: str,
        conversation_id: str,
        user_id: str,
        socket_id: str,
        user_name: str = None
    ) -> bool:
        """Acquire a lock on a conversation. Returns True if lock was acquired."""
        redis = RedisPool.get_client()
        lock_key = f"{LOCK_KEY_PREFIX}:{org_id}:{conversation_id}"

        lock_data = json.dumps({
            "user_id": user_id,
            "socket_id": socket_id,
            "user_name": user_name or "",
            "locked_at": int(datetime.now(timezone.utc).timestamp() * 1000)
        })

        # SET with NX (only if not exists) — atomic claim
        acquired = await redis.set(lock_key, lock_data, nx=True, ex=LOCK_TTL_SECONDS)
        if not acquired:
            # Check if it's already locked by the same user (reconnect case)
            existing = await redis.get(lock_key)
            if existing:
                existing_data = json.loads(existing)
                if existing_data.get("user_id") == user_id:
                    # Re-acquire: update socket_id
                    await redis.set(lock_key, lock_data, ex=LOCK_TTL_SECONDS)
                    acquired = True

        if acquired:
            # Register in org index
            org_index_key = f"{LOCK_ORG_INDEX_PREFIX}:{org_id}:active"
            await redis.sadd(org_index_key, conversation_id)

            # Register in socket index
            socket_index_key = f"{LOCK_SOCKET_PREFIX}:{socket_id}"
            await redis.sadd(socket_index_key, f"{org_id}:{conversation_id}")
            await redis.expire(socket_index_key, LOCK_TTL_SECONDS)

            logger.info(f"Lock acquired: org={org_id}, conv={conversation_id}, user={user_id}")

        return bool(acquired)

    @staticmethod
    async def force_acquire_lock(
        org_id: str,
        conversation_id: str,
        user_id: str,
        socket_id: str,
        user_name: str = None
    ) -> bool:
        """Force-acquire a lock, overwriting any existing lock. Used during handoff grant."""
        redis = RedisPool.get_client()
        lock_key = f"{LOCK_KEY_PREFIX}:{org_id}:{conversation_id}"

        # Remove old lock references first
        existing = await redis.get(lock_key)
        if existing:
            existing_data = json.loads(existing)
            old_socket = existing_data.get("socket_id")
            if old_socket:
                old_socket_key = f"{LOCK_SOCKET_PREFIX}:{old_socket}"
                await redis.srem(old_socket_key, f"{org_id}:{conversation_id}")

        lock_data = json.dumps({
            "user_id": user_id,
            "socket_id": socket_id,
            "user_name": user_name or "",
            "locked_at": int(datetime.now(timezone.utc).timestamp() * 1000)
        })

        await redis.set(lock_key, lock_data, ex=LOCK_TTL_SECONDS)

        # Register in org index
        org_index_key = f"{LOCK_ORG_INDEX_PREFIX}:{org_id}:active"
        await redis.sadd(org_index_key, conversation_id)

        # Register in socket index
        socket_index_key = f"{LOCK_SOCKET_PREFIX}:{socket_id}"
        await redis.sadd(socket_index_key, f"{org_id}:{conversation_id}")
        await redis.expire(socket_index_key, LOCK_TTL_SECONDS)

        logger.info(f"Lock force-acquired: org={org_id}, conv={conversation_id}, user={user_id}")
        return True

    @staticmethod
    async def release_lock(org_id: str, conversation_id: str, socket_id: str = None):
        """Release a lock on a conversation."""
        redis = RedisPool.get_client()
        lock_key = f"{LOCK_KEY_PREFIX}:{org_id}:{conversation_id}"

        if socket_id is None:
            # Read existing lock to get socket_id for cleanup
            existing = await redis.get(lock_key)
            if existing:
                existing_data = json.loads(existing)
                socket_id = existing_data.get("socket_id")

        await redis.delete(lock_key)

        # Remove from org index
        org_index_key = f"{LOCK_ORG_INDEX_PREFIX}:{org_id}:active"
        await redis.srem(org_index_key, conversation_id)

        # Remove from socket index
        if socket_id:
            socket_index_key = f"{LOCK_SOCKET_PREFIX}:{socket_id}"
            await redis.srem(socket_index_key, f"{org_id}:{conversation_id}")

        logger.info(f"Lock released: org={org_id}, conv={conversation_id}")

    @staticmethod
    async def release_all_locks_for_socket(socket_id: str) -> list[dict]:
        """Release all locks held by a specific socket. Returns list of released lock details."""
        redis = RedisPool.get_client()
        socket_index_key = f"{LOCK_SOCKET_PREFIX}:{socket_id}"
        entries = await redis.smembers(socket_index_key)

        released = []
        for entry in entries:
            try:
                org_id, conversation_id = entry.split(":", 1)
                lock_key = f"{LOCK_KEY_PREFIX}:{org_id}:{conversation_id}"
                existing = await redis.get(lock_key)
                if existing:
                    existing_data = json.loads(existing)
                    # Only release if socket matches (prevent race condition)
                    if existing_data.get("socket_id") == socket_id:
                        await redis.delete(lock_key)
                        org_index_key = f"{LOCK_ORG_INDEX_PREFIX}:{org_id}:active"
                        await redis.srem(org_index_key, conversation_id)
                        released.append({
                            "org_id": org_id,
                            "conversation_id": conversation_id,
                            "user_id": existing_data.get("user_id")
                        })
            except Exception as e:
                logger.error(f"Error releasing lock for socket entry '{entry}': {e}")

        await redis.delete(socket_index_key)
        logger.info(f"Released {len(released)} locks for socket {socket_id}")
        return released

    @staticmethod
    async def get_lock(org_id: str, conversation_id: str) -> dict | None:
        """Get the current lock details for a conversation."""
        redis = RedisPool.get_client()
        lock_key = f"{LOCK_KEY_PREFIX}:{org_id}:{conversation_id}"
        data = await redis.get(lock_key)
        if data:
            return json.loads(data)
        return None

    @staticmethod
    async def get_active_locks_for_org(org_id: str) -> dict[str, dict]:
        """
        Get all active locks for an organization.
        Returns dict mapping conversation_id -> lock data.
        """
        redis = RedisPool.get_client()
        org_index_key = f"{LOCK_ORG_INDEX_PREFIX}:{org_id}:active"
        conversation_ids = await redis.smembers(org_index_key)

        if not conversation_ids:
            return {}

        # Pipeline fetch all lock keys
        pipe = redis.pipeline()
        cid_list = list(conversation_ids)
        for cid in cid_list:
            pipe.get(f"{LOCK_KEY_PREFIX}:{org_id}:{cid}")
        results = await pipe.execute()

        locks = {}
        stale_ids = []
        for cid, data in zip(cid_list, results):
            if data:
                locks[cid] = json.loads(data)
            else:
                stale_ids.append(cid)

        # Clean up stale index entries
        if stale_ids:
            pipe = redis.pipeline()
            for cid in stale_ids:
                pipe.srem(org_index_key, cid)
            await pipe.execute()

        return locks


class ChatHandoffService:
    """
    Manages peer-to-peer handoff requests between team members.
    """

    @staticmethod
    async def request_handoff(
        conversation_id: str,
        requester_id: str,
        requester_name: str,
        handler_id: str,
        org_id: str
    ) -> dict:
        """
        Create a pending handoff request and send a DM notification to the handler.
        Returns the handoff request record.
        """
        handoff = HandoffRequestDetail(
            conversation_id=conversation_id,
            requester_id=requester_id,
            handler_id=handler_id,
            org_id=org_id,
            status="pending"
        )

        # Build the notification message to be sent as a DM
        message_text = f"🔄 {requester_name} is requesting to take over a customer conversation."

        # Publish to internal_chat.direct topic — the worker will persist and fan out
        dm_event = {
            "org_id": org_id,
            "sender_id": requester_id,
            "sender_name": requester_name,
            "recipient_id": handler_id,
            "text": message_text,
            "message_type": "handoff_request",
            "handoff_request": handoff.model_dump(mode="json")
        }

        await KafkaProducerPool.send_message("internal_chat.direct", dm_event)
        logger.info(f"Handoff requested: id={handoff.id}, requester={requester_id}, handler={handler_id}, conv={conversation_id}")

        # Broadcast pending state to the customer chat room (chat_websocket)
        from bson import ObjectId
        try:
            customer_conv = await mongo_db.conversations.find_one({"_id": ObjectId(conversation_id)})
            if customer_conv:
                lock_ws_payload = {
                    "org_id": org_id,
                    "type": "handoff_status_updated",
                    "conversation_id": conversation_id,
                    "platform": customer_conv["platform"],
                    "sender_id": str(customer_conv["user"]["sender_id"]),
                    "status": "pending"
                }
                await KafkaProducerPool.send_message("chat_websocket", lock_ws_payload)
        except Exception as ws_err:
            logger.warning(f"Failed to broadcast handoff_status_updated on request: {ws_err}")

        # Schedule expiration
        asyncio.get_event_loop().call_later(
            HANDOFF_EXPIRY_SECONDS,
            lambda: asyncio.create_task(ChatHandoffService.expire_handoff(handoff.id, org_id, requester_id, handler_id))
        )

        return handoff.model_dump(mode="json")

    @staticmethod
    async def grant_handoff(
        handoff_id: str,
        org_id: str,
        handler_id: str,
        handler_name: str,
        handler_socket_id: str
    ) -> dict:
        """
        Grant a handoff request:
        1. Find the handoff record in MongoDB and validate
        2. Release the lock from the handler and transfer it to the requester
        3. Update the handoff status to "granted"
        4. Broadcast lock update and handoff status update
        """
        mongo_db = MongoDBManager.get_db()

        # Find the handoff record across direct conversations
        conv = await mongo_db.internal_conversations.find_one({
            "messages.handoff_request.id": handoff_id
        })
        if not conv:
            return {"error": "Handoff request not found."}

        # Find the specific message
        handoff_msg = None
        handoff_data = None
        for msg in conv.get("messages", []):
            hr = msg.get("handoff_request")
            if hr and hr.get("id") == handoff_id:
                handoff_msg = msg
                handoff_data = hr
                break

        if not handoff_data:
            return {"error": "Handoff request not found."}

        if handoff_data.get("status") != "pending":
            return {"error": f"Handoff request is already {handoff_data.get('status')}."}

        # Validate handler matches
        if handoff_data.get("handler_id") != handler_id:
            return {"error": "You are not the handler of this conversation."}

        requester_id = handoff_data["requester_id"]
        conversation_id = handoff_data["conversation_id"]

        # Atomically transfer lock in Redis:
        # 1. Release handler's lock
        await ChatLockManager.release_lock(org_id, conversation_id)

        # Resolve requester's name from PostgreSQL
        requester_name = None
        try:
            from sqlalchemy import select
            from shared.database.schema.users import User
            from shared.database.engine import SessionLocal
            from uuid import UUID
            async with SessionLocal() as db_session:
                user_stmt = select(User).where(User.id == UUID(requester_id))
                user_result = await db_session.execute(user_stmt)
                db_user = user_result.scalar_one_or_none()
                requester_name = db_user.full_name if db_user else None
        except Exception as e:
            logger.warning(f"Failed to resolve requester name during handoff grant: {e}")

        # 1b. Force acquire lock for requester in Redis
        try:
            await ChatLockManager.force_acquire_lock(
                org_id=org_id,
                conversation_id=conversation_id,
                user_id=requester_id,
                socket_id=handler_socket_id,
                user_name=requester_name
            )
        except Exception as lock_err:
            logger.warning(f"Failed to force acquire lock for requester: {lock_err}")

        # 2. Also update MongoDB bot_id to the requester
        # Find the customer conversation by its _id or platform/sender_id
        from bson import ObjectId
        try:
            customer_conv = await mongo_db.conversations.find_one({"_id": ObjectId(conversation_id)})
        except Exception:
            # conversation_id might be a composite key — search by platform+sender_id
            customer_conv = None

        if customer_conv:
            await mongo_db.conversations.update_one(
                {"_id": customer_conv["_id"]},
                {"$set": {
                    "bot_id": requester_id,
                    "ai_assigned": False,
                    "updated_at": datetime.now(timezone.utc)
                }}
            )

        # 3. Update handoff status in MongoDB
        await mongo_db.internal_conversations.update_one(
            {"messages.handoff_request.id": handoff_id},
            {"$set": {"messages.$[elem].handoff_request.status": "granted"}},
            array_filters=[{"elem.handoff_request.id": handoff_id}]
        )

        # 4. Broadcast handoff status update via Kafka -> internal_chat_websocket
        ws_payload = {
            "org_id": org_id,
            "type": "direct",
            "convo_id": str(conv["_id"]),
            "user_ids": [str(uid) for uid in conv.get("user_ids", [])],
            "event_type": "handoff_status_updated",
            "handoff_id": handoff_id,
            "status": "granted",
            "conversation_id": conversation_id
        }
        await KafkaProducerPool.send_message("internal_chat_websocket", ws_payload)

        # 5. Broadcast chat_lock_update to the org room (via chat_websocket)
        lock_ws_payload = {
            "org_id": org_id,
            "type": "chat_lock_update",
            "conversation_id": conversation_id,
            "platform": customer_conv["platform"] if customer_conv else None,
            "sender_id": str(customer_conv["user"]["sender_id"]) if customer_conv else None,
            "bot_id": requester_id,
            "locker_name": requester_name
        }
        await KafkaProducerPool.send_message("chat_websocket", lock_ws_payload)

        logger.info(f"Handoff granted: id={handoff_id}, from={handler_id}, to={requester_id}")
        return {"success": True, "status": "granted", "new_owner": requester_id}

    @staticmethod
    async def decline_handoff(
        handoff_id: str,
        org_id: str,
        handler_id: str
    ) -> dict:
        """Decline a handoff request."""
        mongo_db = MongoDBManager.get_db()

        conv = await mongo_db.internal_conversations.find_one({
            "messages.handoff_request.id": handoff_id
        })
        if not conv:
            return {"error": "Handoff request not found."}

        # Validate and update
        handoff_data = None
        for msg in conv.get("messages", []):
            hr = msg.get("handoff_request")
            if hr and hr.get("id") == handoff_id:
                handoff_data = hr
                break

        if not handoff_data:
            return {"error": "Handoff request not found."}

        if handoff_data.get("status") != "pending":
            return {"error": f"Handoff request is already {handoff_data.get('status')}."}

        if handoff_data.get("handler_id") != handler_id:
            return {"error": "You are not the handler of this conversation."}

        await mongo_db.internal_conversations.update_one(
            {"messages.handoff_request.id": handoff_id},
            {"$set": {"messages.$[elem].handoff_request.status": "declined"}},
            array_filters=[{"elem.handoff_request.id": handoff_id}]
        )

        # Broadcast status update
        ws_payload = {
            "org_id": org_id,
            "type": "direct",
            "convo_id": str(conv["_id"]),
            "user_ids": [str(uid) for uid in conv.get("user_ids", [])],
            "event_type": "handoff_status_updated",
            "handoff_id": handoff_id,
            "status": "declined"
        }
        await KafkaProducerPool.send_message("internal_chat_websocket", ws_payload)

        # Broadcast to chat_websocket for customer inbox real-time update
        conversation_id = handoff_data["conversation_id"]
        from bson import ObjectId
        try:
            customer_conv = await mongo_db.conversations.find_one({"_id": ObjectId(conversation_id)})
            if customer_conv:
                lock_ws_payload = {
                    "org_id": org_id,
                    "type": "handoff_status_updated",
                    "conversation_id": conversation_id,
                    "platform": customer_conv["platform"],
                    "sender_id": str(customer_conv["user"]["sender_id"]),
                    "status": "declined"
                }
                await KafkaProducerPool.send_message("chat_websocket", lock_ws_payload)
        except Exception as ws_err:
            logger.warning(f"Failed to broadcast handoff_status_updated to chat_websocket on decline: {ws_err}")

        logger.info(f"Handoff declined: id={handoff_id}, handler={handler_id}")
        return {"success": True, "status": "declined"}

    @staticmethod
    async def expire_handoff(
        handoff_id: str,
        org_id: str,
        requester_id: str,
        handler_id: str
    ):
        """Auto-expire a handoff request if still pending after timeout."""
        try:
            mongo_db = MongoDBManager.get_db()

            conv = await mongo_db.internal_conversations.find_one({
                "messages.handoff_request.id": handoff_id
            })
            if not conv:
                return

            # Check if still pending
            handoff_data = None
            for msg in conv.get("messages", []):
                hr = msg.get("handoff_request")
                if hr and hr.get("id") == handoff_id:
                    handoff_data = hr
                    break

            if not handoff_data or handoff_data.get("status") != "pending":
                return  # Already resolved

            await mongo_db.internal_conversations.update_one(
                {"messages.handoff_request.id": handoff_id},
                {"$set": {"messages.$[elem].handoff_request.status": "expired"}},
                array_filters=[{"elem.handoff_request.id": handoff_id}]
            )

            # Broadcast expiry
            ws_payload = {
                "org_id": org_id,
                "type": "direct",
                "convo_id": str(conv["_id"]),
                "user_ids": [str(requester_id), str(handler_id)],
                "event_type": "handoff_status_updated",
                "handoff_id": handoff_id,
                "status": "expired"
            }
            await KafkaProducerPool.send_message("internal_chat_websocket", ws_payload)

            # Broadcast to chat_websocket for customer inbox real-time update
            conversation_id = handoff_data["conversation_id"]
            from bson import ObjectId
            try:
                customer_conv = await mongo_db.conversations.find_one({"_id": ObjectId(conversation_id)})
                if customer_conv:
                    lock_ws_payload = {
                        "org_id": org_id,
                        "type": "handoff_status_updated",
                        "conversation_id": conversation_id,
                        "platform": customer_conv["platform"],
                        "sender_id": str(customer_conv["user"]["sender_id"]),
                        "status": "expired"
                    }
                    await KafkaProducerPool.send_message("chat_websocket", lock_ws_payload)
            except Exception as ws_err:
                logger.warning(f"Failed to broadcast handoff_status_updated to chat_websocket on expire: {ws_err}")

            logger.info(f"Handoff expired: id={handoff_id}")
        except Exception as e:
            logger.error(f"Error expiring handoff {handoff_id}: {e}", exc_info=True)


async def get_eligible_online_users(org_id: str, db: "AsyncSession", presence_service: "PresenceService", exclude_user_id: str) -> list["User"]:
    """Query and filter online users in the org who have 'chats' permission."""
    from sqlalchemy.ext.asyncio import AsyncSession
    from shared.database.schema.users import User
    from services.api_gateway.routers.presence.presence_service import PresenceService
    from sqlalchemy import select
    from uuid import UUID

    # 1. Get all online users for this org (within 5 mins)
    online_user_ids = await presence_service.get_org_online_users(org_id, within_seconds=300)
    if not online_user_ids:
        return []

    # 2. Get active users from PostgreSQL
    user_uuids = []
    for uid in online_user_ids:
        if str(uid) == str(exclude_user_id):
            continue
        try:
            user_uuids.append(UUID(uid))
        except Exception:
            pass
            
    if not user_uuids:
        return []
        
    try:
        org_uuid = UUID(org_id)
    except ValueError:
        return []
        
    stmt = select(User).where(
        User.organization_id == org_uuid,
        User.id.in_(user_uuids),
        User.is_active == True
    )
    res = await db.execute(stmt)
    users = res.scalars().all()
    
    # 3. Filter users who have "chats" permission
    from services.api_gateway.routers.auth_routers.me import get_user_permissions
    eligible_users = []
    for user in users:
        role_str = user.role.value if hasattr(user.role, 'value') else str(user.role)
        perms = await get_user_permissions(db, str(user.id), role_str)
        if "chats" in perms:
            eligible_users.append(user)
            
    return eligible_users


async def handle_user_offline(org_id: str, user_id: str):
    """
    Called when a user goes offline.
    Finds all active chats handled by this user (where bot_id == user_id),
    and if there are online users with "chats" permission, re-assigns them
    to one online user. Otherwise, unlocks the chat.
    """
    logger.info(f"Handling offline event for user {user_id} in org {org_id}")
    
    try:
        from shared.database.engine import SessionLocal
        from services.api_gateway.routers.presence.presence_service import PresenceService
        
        mongo_db = MongoDBManager.get_db()
        presence_service = PresenceService()
        
        # 1. Find all conversations handled by this user
        cursor = mongo_db.conversations.find({
            "organization_id": org_id,
            "bot_id": user_id
        })
        conversations = await cursor.to_list(length=100)
        
        if not conversations:
            logger.info(f"No active conversations locked by offline user {user_id}")
            return
            
        # 2. Query eligible online users who have "chats" permission
        eligible_users = []
        async with SessionLocal() as db_session:
            eligible_users = await get_eligible_online_users(org_id, db_session, presence_service, exclude_user_id=user_id)
            
        if eligible_users:
            # Pick one online user (the first one)
            new_user = eligible_users[0]
            new_user_id = str(new_user.id)
            new_user_name = new_user.full_name
            logger.info(f"Re-assigning {len(conversations)} chats from offline user {user_id} to online user {new_user_id} ({new_user_name})")
            
            for conv in conversations:
                conv_id = str(conv["_id"])
                platform = conv["platform"]
                sender_id = str(conv["user"]["sender_id"])
                
                # Release existing Redis lock (if any) and force acquire for the new user
                try:
                    await ChatLockManager.release_lock(org_id, conv_id)
                    from services.api_gateway.routers.chat_routers.chats import manager
                    socket_id = manager.find_socket_id(new_user_id, platform, sender_id) or f"fallback-offline-{uuid4()}"
                    
                    await ChatLockManager.force_acquire_lock(
                        org_id=org_id,
                        conversation_id=conv_id,
                        user_id=new_user_id,
                        socket_id=socket_id,
                        user_name=new_user_name
                    )
                except Exception as lock_err:
                    logger.warning(f"Failed to transfer Redis lock for conv {conv_id}: {lock_err}")
                
                # Update MongoDB bot_id to the new user and set ai_assigned = False
                await mongo_db.conversations.update_one(
                    {"_id": conv["_id"]},
                    {"$set": {
                        "bot_id": new_user_id,
                        "ai_assigned": False,
                        "updated_at": datetime.now(timezone.utc)
                    }}
                )
                
                # Broadcast the lock status update to WebSocket clients in the org
                try:
                    from services.api_gateway.routers.chat_routers.chats import manager
                    ws_event = {
                        "org_id": org_id,
                        "platform": platform,
                        "sender_id": sender_id,
                        "type": "chat_lock_update",
                        "bot_id": new_user_id,
                        "locker_name": new_user_name
                    }
                    await manager.broadcast(org_id, ws_event)
                except Exception as ws_err:
                    logger.error(f"Failed to broadcast lock update on offline handoff: {ws_err}")
        else:
            # No online users are available, unlock all conversations (bot_id = None)
            logger.info(f"No online users with chats permission. Unlocking {len(conversations)} chats.")
            for conv in conversations:
                conv_id = str(conv["_id"])
                platform = conv["platform"]
                sender_id = str(conv["user"]["sender_id"])
                
                try:
                    await ChatLockManager.release_lock(org_id, conv_id)
                except Exception as lock_err:
                    logger.warning(f"Failed to release Redis lock for conv {conv_id}: {lock_err}")
                    
                await mongo_db.conversations.update_one(
                    {"_id": conv["_id"]},
                    {"$set": {
                        "bot_id": None,
                        "ai_assigned": False,
                        "updated_at": datetime.now(timezone.utc)
                    }}
                )
                
                try:
                    from services.api_gateway.routers.chat_routers.chats import manager
                    ws_event = {
                        "org_id": org_id,
                        "platform": platform,
                        "sender_id": sender_id,
                        "type": "chat_lock_update",
                        "bot_id": None,
                        "locker_name": None
                    }
                    await manager.broadcast(org_id, ws_event)
                except Exception as ws_err:
                    logger.error(f"Failed to broadcast lock update on offline unlock: {ws_err}")
    except Exception as e:
        logger.error(f"Error handling user offline lock releases: {e}", exc_info=True)
