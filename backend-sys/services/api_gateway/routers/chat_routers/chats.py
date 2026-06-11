from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form, Request
from typing import Optional, List, Union
from datetime import datetime, timezone
from shared.database.mongodb import MongoDBManager
from sqlalchemy.ext.asyncio import AsyncSession
from shared.database.engine import SessionLocal
from shared.database.schema.platform_connectors import PlatformConnector
from sqlalchemy import select
from pydantic import BaseModel
from services.api_gateway.routers.teams.permissions import check_permission
from shared.database.schema.users import User, UserRole
from uuid import UUID, uuid4
import logging
from services.api_gateway.routers.chat_routers.handoff_service import ChatLockManager, ChatHandoffService

logger = logging.getLogger("api_gateway.chats")

async def check_chat_access(platform: str, sender_id: Union[int, str], user_id: str, db_session: AsyncSession) -> bool:
    mongo_db = MongoDBManager.get_db()
    sender_id_int = int(sender_id) if str(sender_id).isdigit() else None
    query_id = {"$in": [sender_id, sender_id_int]} if sender_id_int is not None else sender_id
    
    # 1. Fetch user to check role and permissions
    user_stmt = select(User).where(User.id == UUID(user_id))
    user_result = await db_session.execute(user_stmt)
    db_user = user_result.scalar_one_or_none()
    if not db_user:
        return False

    role = db_user.role.value if hasattr(db_user.role, 'value') else str(db_user.role)
    role = role.upper()

    # If the user is not OWNER, check if they have "chats" permission
    if role != "OWNER":
        from services.api_gateway.routers.auth_routers.me import get_user_permissions
        permissions = await get_user_permissions(db_session, user_id, role)
        if "chats" not in permissions:
            return False

    conv = await mongo_db.conversations.find_one({
        "platform": platform.lower(),
        "user.sender_id": query_id
    })
    if not conv:
        # If no conversation exists yet, but they are authorized for chats, they can access
        return True

    # 2. Check organization boundaries
    if str(conv.get("organization_id", "")) != str(db_user.organization_id):
        return False

    # 3. Check assignment boundaries
    assigned_user = conv.get("assigned_user")
    if assigned_user:
        allowed_users = conv.get("allowed_users", [])
        if str(user_id) in [str(u) for u in allowed_users]:
            return True
        return str(assigned_user) == str(user_id) or role == "OWNER"

    # If unassigned, any authorized user (OWNER or someone with "chats" permission) is allowed
    return True


async def get_user_name_by_id(db_session: AsyncSession, user_id_str: str) -> Optional[str]:
    if not user_id_str:
        return None
    try:
        from uuid import UUID
        user_uuid = UUID(user_id_str)
        user_stmt = select(User).where(User.id == user_uuid)
        user_result = await db_session.execute(user_stmt)
        db_user = user_result.scalar_one_or_none()
        return db_user.full_name if db_user else None
    except Exception:
        return None


router = APIRouter(prefix="/api/chats", tags=["Chat Management"])

async def get_db():
    async with SessionLocal() as session:
        yield session

class SendReplyRequest(BaseModel):
    sender_id: Union[int, str]
    platform: str
    text: str

class AssignChatRequest(BaseModel):
    sender_id: Union[int, str]
    platform: str
    assigned_user_id: Optional[str] = None


class ToggleAIAssignedRequest(BaseModel):
    sender_id: Union[int, str]
    platform: str
    ai_assigned: bool

class LockChatRequest(BaseModel):
    sender_id: Union[int, str]
    platform: str
    bot_id: Optional[str] = None

class HandoffRequestModel(BaseModel):
    platform: str
    sender_id: Union[int, str]

class HandoffRespondModel(BaseModel):
    handoff_id: str
    action: str  # "grant" or "decline"

@router.get("")
async def get_chat_list(
    organization_id: Optional[str] = None,
    current_user: dict = Depends(check_permission("chats")),
    db_session: AsyncSession = Depends(get_db)
):
    """
    Get all conversations/chats, optionally filtered by organization_id.
    """
    try:
        db = MongoDBManager.get_db()
        query = {}
        org_filter = organization_id or current_user["organization_id"]
        if org_filter:
            query["organization_id"] = org_filter
            
        # Retrieve all conversations, sorted by updated_at descending
        cursor = db.conversations.find(query).sort("updated_at", -1)
        
        # Fetch active Redis locks for this org
        try:
            active_locks = await ChatLockManager.get_active_locks_for_org(org_filter)
        except Exception as lock_err:
            logger.warning(f"Failed to fetch Redis locks for org {org_filter}: {lock_err}")
            active_locks = {}

        # Fetch all pending handoff requests for this org
        pending_conv_ids = set()
        try:
            cursor_pending = db.internal_conversations.find({
                "org_id": org_filter,
                "messages": {
                    "$elemMatch": {
                        "handoff_request.status": "pending"
                    }
                }
            })
            async for pending_doc in cursor_pending:
                for msg in pending_doc.get("messages", []):
                    hr = msg.get("handoff_request")
                    if hr and hr.get("status") == "pending":
                        pending_conv_ids.add(str(hr.get("conversation_id")))
        except Exception as pending_err:
            logger.warning(f"Failed to fetch pending handoffs for org {org_filter}: {pending_err}")

        # Check permissions for viewing handled chats
        has_view_handled = (
            current_user.get("role", "").upper() == "OWNER" or
            "chat:view_handled" in current_user.get("permissions", [])
        )

        chats = []
        bot_ids_to_resolve = set()
        async for doc in cursor:
            # Convert ObjectId to string for JSON serialization
            doc["_id"] = str(doc["_id"])
            # Remove large/binary checkpointer data to avoid serialization errors
            doc.pop("checkpoint", None)
            doc.pop("metadata", None)
            
            # Resolve bot_id (Redis lock takes precedence over MongoDB bot_id)
            conv_id = doc["_id"]
            redis_lock = active_locks.get(conv_id)
            resolved_bot_id = None
            if redis_lock:
                resolved_bot_id = redis_lock.get("user_id")
                doc["bot_id"] = resolved_bot_id
                doc["locker_name"] = redis_lock.get("user_name") or None
                if doc["locker_name"]:
                    pass  # Already resolved from Redis
                else:
                    bot_ids_to_resolve.add(resolved_bot_id)
            else:
                resolved_bot_id = doc.get("bot_id")
                if resolved_bot_id == "ai":
                    doc["locker_name"] = "AI"
                elif resolved_bot_id:
                    bot_ids_to_resolve.add(resolved_bot_id)
                else:
                    doc["locker_name"] = None

            # Enforce "chat:view_handled" permission
            if resolved_bot_id and resolved_bot_id != "ai" and resolved_bot_id != current_user["user_id"]:
                if not has_view_handled:
                    continue
                
            doc["handoff_pending"] = conv_id in pending_conv_ids
            chats.append(doc)
            
        # Resolve names from SQL
        if bot_ids_to_resolve:
            try:
                from uuid import UUID
                uuids = []
                for b_id in bot_ids_to_resolve:
                    try:
                        uuids.append(UUID(b_id))
                    except Exception:
                        pass
                if uuids:
                    stmt = select(User.id, User.full_name).where(User.id.in_(uuids))
                    result = await db_session.execute(stmt)
                    user_map = {str(uid): name for uid, name in result.all()}
                    
                    for doc in chats:
                        b_id = doc.get("bot_id")
                        if b_id and b_id in user_map:
                            doc["locker_name"] = user_map[b_id]
            except Exception as e:
                logger.error(f"Error resolving locker names for chats list: {e}")
                
        return {"success": True, "chats": chats}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve chat list: {str(e)}"
        )

@router.get("/{platform}/{sender_id}")
async def get_chat_history(
    platform: str,
    sender_id: str,
    current_user: dict = Depends(check_permission("chats")),
    db_session: AsyncSession = Depends(get_db)
):
    """
    Get the full message history for a specific conversation by platform and sender_id.
    Enforces user assignment and OWNER fallback restrictions.
    """
    try:
        # Verify access rights
        has_access = await check_chat_access(platform, sender_id, current_user["user_id"], db_session)
        if not has_access:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You are not authorized to view this chat. It is either assigned to another user or you lack OWNER permissions for unassigned chats."
            )

        db = MongoDBManager.get_db()
        sender_id_int = int(sender_id) if str(sender_id).isdigit() else None
        query_id = {"$in": [sender_id, sender_id_int]} if sender_id_int is not None else sender_id

        doc = await db.conversations.find_one({
            "platform": platform.lower(),
            "user.sender_id": query_id
        })
        if not doc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Conversation not found."
            )
        doc["_id"] = str(doc["_id"])
        # Remove large/binary checkpointer data to avoid serialization errors
        doc.pop("checkpoint", None)
        doc.pop("metadata", None)
        
        # Derive lock state from Redis first, fallback to MongoDB bot_id
        conv_id = doc["_id"]
        try:
            redis_lock = await ChatLockManager.get_lock(doc.get("organization_id", current_user["organization_id"]), conv_id)
        except Exception as lock_err:
            logger.warning(f"Failed to fetch Redis lock for conversation {conv_id}: {lock_err}")
            redis_lock = None

        if redis_lock:
            bot_id = redis_lock.get("user_id")
            doc["bot_id"] = bot_id
            doc["locker_name"] = redis_lock.get("user_name") or None
        else:
            bot_id = doc.get("bot_id")
            if bot_id == "ai":
                doc["locker_name"] = "AI"
            elif bot_id:
                doc["locker_name"] = await get_user_name_by_id(db_session, bot_id)
            else:
                doc["locker_name"] = None

        # Check if there is a pending handoff request
        try:
            pending_req = await db.internal_conversations.find_one({
                "messages": {
                    "$elemMatch": {
                        "handoff_request.conversation_id": conv_id,
                        "handoff_request.status": "pending"
                    }
                }
            })
            doc["handoff_pending"] = pending_req is not None
        except Exception:
            doc["handoff_pending"] = False

        # Check permissions for viewing handled chats
        if bot_id and bot_id != "ai" and bot_id != current_user["user_id"]:
            has_view_handled = (
                current_user.get("role", "").upper() == "OWNER" or
                "chat:view_handled" in current_user.get("permissions", [])
            )
            if not has_view_handled:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You are not authorized to view this chat. It is currently handled by another user."
                )
            
        return {"success": True, "chat": doc}
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve chat history: {str(e)}"
        )


@router.post("/reply")
async def send_chat_reply_endpoint(
    req: SendReplyRequest,
    db_session: AsyncSession = Depends(get_db),
    current_user: dict = Depends(check_permission("chats"))
):
    """
    Send a reply to a conversation. Finds the bot token, organization ID, and chat ID
    and publishes the outbound message event to the Kafka topic.
    """
    try:
        # Verify access rights
        has_access = await check_chat_access(req.platform, req.sender_id, current_user["user_id"], db_session)
        if not has_access:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You are not authorized to reply to this chat. It is either assigned to another user or you lack OWNER permissions for unassigned chats."
            )

        # 1. Retrieve conversation from MongoDB to get organization_id, bot_id, and chat_id
        mongo_db = MongoDBManager.get_db()
        sender_id_int = int(req.sender_id) if str(req.sender_id).isdigit() else None
        query_id = {"$in": [req.sender_id, sender_id_int]} if sender_id_int is not None else req.sender_id
        conv = await mongo_db.conversations.find_one({
            "platform": req.platform.lower(),
            "user.sender_id": query_id
        })
        if not conv:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Conversation not found in MongoDB."
            )

        org_id = conv.get("organization_id")
        conv_id = str(conv["_id"])

        # Enforce Lock: check Redis first, fallback to MongoDB
        try:
            redis_lock = await ChatLockManager.get_lock(org_id, conv_id)
        except Exception:
            redis_lock = None

        if redis_lock:
            bot_id = redis_lock.get("user_id")
        else:
            bot_id = conv.get("bot_id")

        allowed_users = conv.get("allowed_users", [])
        is_allowed = str(current_user["user_id"]) in [str(u) for u in allowed_users] or current_user.get("role", "").upper() == "OWNER"
        
        if bot_id and not is_allowed:
            if bot_id == "ai":
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="This conversation is locked by AI. Please disable AI auto-reply to send a message."
                )
            elif bot_id != current_user["user_id"]:
                locker_name = await get_user_name_by_id(db_session, bot_id) or "another agent"
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"This conversation is locked by {locker_name}."
                )

        # Auto-claim lock if unlocked
        if not bot_id:
            bot_id = current_user["user_id"]
            await mongo_db.conversations.update_one(
                {
                    "platform": req.platform.lower(),
                    "user.sender_id": query_id
                },
                {
                    "$set": {
                        "bot_id": bot_id,
                        "ai_assigned": False,
                        "updated_at": datetime.now(timezone.utc)
                    }
                }
            )
            try:
                locker_name = await get_user_name_by_id(db_session, bot_id)
                # Find active socket ID
                socket_id = manager.find_socket_id(bot_id, req.platform, str(req.sender_id)) or f"fallback-{uuid4()}"
                await ChatLockManager.acquire_lock(
                    org_id=org_id,
                    conversation_id=conv_id,
                    user_id=bot_id,
                    socket_id=socket_id,
                    user_name=locker_name
                )
                ws_event = {
                    "org_id": org_id,
                    "platform": req.platform.lower(),
                    "sender_id": req.sender_id,
                    "type": "chat_lock_update",
                    "bot_id": bot_id,
                    "locker_name": locker_name
                }
                await manager.broadcast(org_id, ws_event)
            except Exception as ws_err:
                logger.error(f"Failed to broadcast auto-claim chat_lock_update: {ws_err}")
            
        org_id = conv.get("organization_id")
        chat_id = conv.get("chat_id")
        
        # 2. Look up the connector in PostgreSQL to get the bot_token
        stmt = select(PlatformConnector).where(
            PlatformConnector.platform == req.platform.lower()
        )
        result = await db_session.execute(stmt)
        connectors = result.scalars().all()
        
        connector = None
        for c in connectors:
            if str(c.business_id) == str(org_id):
                connector = c
                break
                
        if not connector:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"No active connector found for platform '{req.platform}' and organization ID '{org_id}'."
            )
            
        # Decrypt token if encrypted
        bot_token = None
        if connector.tokens.get("access_token_encrypted"):
            from shared.utils import decrypt_access_token
            from shared.config import JWT_SECRET
            try:
                bot_token = decrypt_access_token(
                    connector.tokens["token_iv"],
                    connector.tokens["token_ciphertext"],
                    connector.tokens["token_auth_tag"],
                    str(JWT_SECRET)
                )
            except Exception as e:
                logger.error(f"Failed to decrypt Instagram access token: {e}")
        else:
            bot_token = connector.tokens.get("bot_token") or connector.tokens.get("access_token")

        if not bot_token:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Connector is missing the bot token configuration."
            )
            
        bot_name = connector.platform_account_name or "UnknownBot"

        # 3. Publish to Kafka 'chat_service' topic
        import importlib
        _chat_service = importlib.import_module("services.chatai-service.chat_service")
        route_outbound_reply = _chat_service.route_outbound_reply
        await route_outbound_reply(
            org_id=str(org_id),
            bot_name=bot_name,
            bot_token=bot_token,
            platform=req.platform.lower(),
            chat_id=chat_id,
            sender_id=req.sender_id,
            text=req.text,
            ig_account_id=connector.platform_account_id if req.platform.lower() == "instagram" else None,
            assigned_user=current_user["user_id"]
        )
        
        return {"success": True, "message": "Reply event successfully sent to Kafka."}
        
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to send reply: {str(e)}"
        )

class ShareProductsRequest(BaseModel):
    sender_id: Union[int, str]
    platform: str
    product_ids: List[str]

@router.post("/share-products")
async def share_products_endpoint(
    req: ShareProductsRequest,
    request: Request,
    db_session: AsyncSession = Depends(get_db),
    current_user: dict = Depends(check_permission("chats"))
):
    """
    Share one or more products directly by ID. Queries the products details via gRPC and
    publishes the outbound product card events to the Kafka chat_service topic.
    """
    try:
        # Verify access rights
        has_access = await check_chat_access(req.platform, req.sender_id, current_user["user_id"], db_session)
        if not has_access:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You are not authorized to reply to this chat. It is either assigned to another user or you lack OWNER permissions for unassigned chats."
            )

        # 1. Retrieve conversation from MongoDB to get organization_id, bot_id, and chat_id
        mongo_db = MongoDBManager.get_db()
        sender_id_int = int(req.sender_id) if str(req.sender_id).isdigit() else None
        query_id = {"$in": [req.sender_id, sender_id_int]} if sender_id_int is not None else req.sender_id
        conv = await mongo_db.conversations.find_one({
            "platform": req.platform.lower(),
            "user.sender_id": query_id
        })
        if not conv:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Conversation not found in MongoDB."
            )

        org_id = conv.get("organization_id")
        conv_id = str(conv["_id"])

        # Enforce Lock: check Redis first, fallback to MongoDB
        try:
            redis_lock = await ChatLockManager.get_lock(org_id, conv_id)
        except Exception:
            redis_lock = None

        if redis_lock:
            bot_id = redis_lock.get("user_id")
        else:
            bot_id = conv.get("bot_id")

        allowed_users = conv.get("allowed_users", [])
        is_allowed = str(current_user["user_id"]) in [str(u) for u in allowed_users] or current_user.get("role", "").upper() == "OWNER"
        
        if bot_id and not is_allowed:
            if bot_id == "ai":
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="This conversation is locked by AI. Please disable AI auto-reply to send a message."
                )
            elif bot_id != current_user["user_id"]:
                locker_name = await get_user_name_by_id(db_session, bot_id) or "another agent"
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"This conversation is locked by {locker_name}."
                )

        # Auto-claim lock if unlocked
        if not bot_id:
            bot_id = current_user["user_id"]
            await mongo_db.conversations.update_one(
                {
                    "platform": req.platform.lower(),
                    "user.sender_id": query_id
                },
                {
                    "$set": {
                        "bot_id": bot_id,
                        "ai_assigned": False,
                        "updated_at": datetime.now(timezone.utc)
                    }
                }
            )
            try:
                locker_name = await get_user_name_by_id(db_session, bot_id)
                # Find active socket ID
                socket_id = manager.find_socket_id(bot_id, req.platform, str(req.sender_id)) or f"fallback-{uuid4()}"
                await ChatLockManager.acquire_lock(
                    org_id=org_id,
                    conversation_id=conv_id,
                    user_id=bot_id,
                    socket_id=socket_id,
                    user_name=locker_name
                )
                ws_event = {
                    "org_id": org_id,
                    "platform": req.platform.lower(),
                    "sender_id": req.sender_id,
                    "type": "chat_lock_update",
                    "bot_id": bot_id,
                    "locker_name": locker_name
                }
                await manager.broadcast(org_id, ws_event)
            except Exception as ws_err:
                logger.error(f"Failed to broadcast auto-claim chat_lock_update: {ws_err}")
            
        org_id = conv.get("organization_id")
        chat_id = conv.get("chat_id")
        
        # 2. Look up the connector in PostgreSQL to get the bot_token
        stmt = select(PlatformConnector).where(
            PlatformConnector.platform == req.platform.lower()
        )
        result = await db_session.execute(stmt)
        connectors = result.scalars().all()
        
        connector = None
        for c in connectors:
            if str(c.business_id) == str(org_id):
                connector = c
                break
                
        if not connector:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"No active connector found for platform '{req.platform}' and organization ID '{org_id}'."
            )
            
        # Decrypt token if encrypted
        bot_token = None
        if connector.tokens.get("access_token_encrypted"):
            from shared.utils import decrypt_access_token
            from shared.config import JWT_SECRET
            try:
                bot_token = decrypt_access_token(
                    connector.tokens["token_iv"],
                    connector.tokens["token_ciphertext"],
                    connector.tokens["token_auth_tag"],
                    str(JWT_SECRET)
                )
            except Exception as e:
                logger.error(f"Failed to decrypt Instagram access token: {e}")
        else:
            bot_token = connector.tokens.get("bot_token") or connector.tokens.get("access_token")

        if not bot_token:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Connector is missing the bot token configuration."
            )
            
        bot_name = connector.platform_account_name or "UnknownBot"

        # 3. Fetch product details and publish product_card events to Kafka
        from shared.proto import service_pb2
        import json
        import importlib
        _chat_service = importlib.import_module("services.chatai-service.chat_service")
        route_outbound_reply = _chat_service.route_outbound_reply

        for pid in req.product_ids:
            try:
                grpc_req = service_pb2.GetProductDetailRequest(
                    organization_id=str(org_id),
                    product_id=str(pid)
                )
                res = await request.app.state.product_stub.GetProductDetail(grpc_req)
                if not res.success or not res.product:
                    logger.warning(f"Product not found when sharing: {pid}")
                    continue
                
                # Format product dict
                p = res.product
                meta_dict = None
                if p.metadata_json:
                    try:
                        meta_dict = json.loads(p.metadata_json)
                    except Exception:
                        pass
                
                product_dict = {
                    "id": p.id,
                    "organization_id": p.organization_id,
                    "name": p.name,
                    "description": p.description if p.description else None,
                    "price": p.price,
                    "currency": p.currency,
                    "stock": p.stock,
                    "sku": p.sku if p.sku else None,
                    "image": p.image if p.image else None,
                    "is_active": p.is_active,
                    "created_at": p.created_at,
                    "updated_at": p.updated_at,
                    "metadata": meta_dict
                }

                # Publish product card event
                await route_outbound_reply(
                    org_id=str(org_id),
                    bot_name=bot_name,
                    bot_token=bot_token,
                    platform=req.platform.lower(),
                    chat_id=chat_id,
                    sender_id=req.sender_id,
                    text="Shared a product card",
                    ig_account_id=connector.platform_account_id if req.platform.lower() == "instagram" else None,
                    assigned_user=current_user["user_id"],
                    message_type="product_card",
                    product_data=product_dict
                )
            except Exception as prod_err:
                logger.error(f"Error sharing product card for {pid}: {prod_err}", exc_info=True)

        return {"success": True, "message": "Product card sharing events successfully sent to Kafka."}
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to share products: {str(e)}"
        )

@router.post("/reply-image")
async def send_chat_reply_image(
    sender_id: str = Form(...),
    platform: str = Form(...),
    image_file: Optional[UploadFile] = File(None),
    image_files: Optional[List[UploadFile]] = File(None),
    db_session: AsyncSession = Depends(get_db),
    current_user: dict = Depends(check_permission("chats"))
):
    """
    Send a reply with one or more images. Uploads each image to Cloudinary first,
    then publishes the events to Kafka to be processed by chatai-service (sent to Telegram/MongoDB).
    """
    try:
        # Verify access rights
        has_access = await check_chat_access(platform, sender_id, current_user["user_id"], db_session)
        if not has_access:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You are not authorized to reply to this chat. It is either assigned to another user or you lack OWNER permissions for unassigned chats."
            )

        # 1. Retrieve conversation from MongoDB to get organization_id, bot_id, and chat_id
        mongo_db = MongoDBManager.get_db()
        sender_id_int = int(sender_id) if str(sender_id).isdigit() else None
        query_id = {"$in": [sender_id, sender_id_int]} if sender_id_int is not None else sender_id
        conv = await mongo_db.conversations.find_one({
            "platform": platform.lower(),
            "user.sender_id": query_id
        })
        if not conv:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Conversation not found in MongoDB."
            )

        org_id = conv.get("organization_id")
        conv_id = str(conv["_id"])

        # Enforce Lock: check Redis first, fallback to MongoDB
        try:
            redis_lock = await ChatLockManager.get_lock(org_id, conv_id)
        except Exception:
            redis_lock = None

        if redis_lock:
            bot_id = redis_lock.get("user_id")
        else:
            bot_id = conv.get("bot_id")

        allowed_users = conv.get("allowed_users", [])
        is_allowed = str(current_user["user_id"]) in [str(u) for u in allowed_users] or current_user.get("role", "").upper() == "OWNER"
        
        if bot_id and not is_allowed:
            if bot_id == "ai":
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="This conversation is locked by AI. Please disable AI auto-reply to send a message."
                )
            elif bot_id != current_user["user_id"]:
                locker_name = await get_user_name_by_id(db_session, bot_id) or "another agent"
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"This conversation is locked by {locker_name}."
                )

        # Auto-claim lock if unlocked
        if not bot_id:
            bot_id = current_user["user_id"]
            await mongo_db.conversations.update_one(
                {
                    "platform": platform.lower(),
                    "user.sender_id": query_id
                },
                {
                    "$set": {
                        "bot_id": bot_id,
                        "ai_assigned": False,
                        "updated_at": datetime.now(timezone.utc)
                    }
                }
            )
            try:
                locker_name = await get_user_name_by_id(db_session, bot_id)
                # Find active socket ID
                socket_id = manager.find_socket_id(bot_id, platform, str(sender_id)) or f"fallback-{uuid4()}"
                await ChatLockManager.acquire_lock(
                    org_id=org_id,
                    conversation_id=conv_id,
                    user_id=bot_id,
                    socket_id=socket_id,
                    user_name=locker_name
                )
                ws_event = {
                    "org_id": org_id,
                    "platform": platform.lower(),
                    "sender_id": sender_id,
                    "type": "chat_lock_update",
                    "bot_id": bot_id,
                    "locker_name": locker_name
                }
                await manager.broadcast(org_id, ws_event)
            except Exception as ws_err:
                logger.error(f"Failed to broadcast auto-claim chat_lock_update: {ws_err}")
            
        org_id = conv.get("organization_id")
        chat_id = conv.get("chat_id")
        
        # 2. Look up the connector in PostgreSQL to get the bot_token
        stmt = select(PlatformConnector).where(
            PlatformConnector.platform == platform.lower()
        )
        result = await db_session.execute(stmt)
        connectors = result.scalars().all()
        
        connector = None
        for c in connectors:
            if str(c.business_id) == str(org_id):
                connector = c
                break
                
        if not connector:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"No active connector found for platform '{platform}' and organization ID '{org_id}'."
            )
            
        bot_name = connector.platform_account_name or "UnknownBot"
            
        # Decrypt token if encrypted
        bot_token = None
        if connector.tokens.get("access_token_encrypted"):
            from shared.utils import decrypt_access_token
            from shared.config import JWT_SECRET
            try:
                bot_token = decrypt_access_token(
                    connector.tokens["token_iv"],
                    connector.tokens["token_ciphertext"],
                    connector.tokens["token_auth_tag"],
                    str(JWT_SECRET)
                )
            except Exception as e:
                logger.error(f"Failed to decrypt Instagram access token: {e}")
        else:
            bot_token = connector.tokens.get("bot_token") or connector.tokens.get("access_token")

        if not bot_token:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Connector is missing the bot token configuration."
            )

        # Collect files
        files = []
        if image_files:
            files.extend(image_files)
        if image_file:
            files.append(image_file)

        if not files:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="At least one image file must be provided."
            )

        from shared.utils import upload_cloudinary_image
        import importlib
        _chat_service = importlib.import_module("services.chatai-service.chat_service")
        route_outbound_reply = _chat_service.route_outbound_reply

        uploaded_urls = []
        for file in files:
            image_url = await upload_cloudinary_image(
                file,
                current_user["organization_id"],
                current_user["organization_name"]
            )
            if not image_url:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to upload image to Cloudinary."
                )
            uploaded_urls.append(image_url)

            # Publish to Kafka 'chat_service' topic
            await route_outbound_reply(
                org_id=str(org_id),
                bot_name=bot_name,
                bot_token=bot_token,
                platform=platform.lower(),
                chat_id=chat_id,
                sender_id=sender_id,
                text="",
                image_url=image_url,
                ig_account_id=connector.platform_account_id if platform.lower() == "instagram" else None,
                assigned_user=current_user["user_id"]
            )
            
        return {"success": True, "image_urls": uploaded_urls, "image_url": uploaded_urls[0]}
        
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to send reply with image: {str(e)}"
        )

@router.post("/assign")
async def assign_chat_user(
    req: AssignChatRequest,
    current_user: dict = Depends(check_permission("chats")),
    db_session: AsyncSession = Depends(get_db)
):
    """
    Endpoint to assign an agent/user to a conversation. Only organization owners can perform assignments.
    """
    if current_user["role"] != "OWNER" and current_user["role"] != UserRole.OWNER.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only organization owners can assign users to conversations."
        )

    try:
        mongo_db = MongoDBManager.get_db()
        sender_id_int = int(req.sender_id) if str(req.sender_id).isdigit() else None
        query_id = {"$in": [req.sender_id, sender_id_int]} if sender_id_int is not None else req.sender_id
        conv = await mongo_db.conversations.find_one({
            "platform": req.platform.lower(),
            "user.sender_id": query_id
        })
        if not conv:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Conversation not found."
            )

        # Update assignment
        await mongo_db.conversations.update_one(
            {
                "platform": req.platform.lower(),
                "user.sender_id": query_id
            },
            {
                "$set": {
                    "assigned_user": req.assigned_user_id,
                    "updated_at": datetime.now(timezone.utc)
                }
            }
        )

        # Broadcast the assignment update via WebSocket
        try:
            ws_event = {
                "org_id": conv.get("organization_id"),
                "platform": req.platform.lower(),
                "sender_id": req.sender_id,
                "type": "chat_assigned_update",
                "assigned_user": req.assigned_user_id
            }
            await manager.broadcast(conv.get("organization_id"), ws_event)
        except Exception as ws_err:
            logger.error(f"Failed to broadcast chat_assigned_update: {ws_err}")

        return {"success": True, "assigned_user": req.assigned_user_id}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to assign user: {str(e)}"
        )

@router.post("/toggle-ai")
async def toggle_ai_assigned(
    req: ToggleAIAssignedRequest,
    current_user: dict = Depends(check_permission("chats"))
):
    """
    Toggle the ai_assigned flag for a specific conversation by platform and sender_id.
    """
    try:
        mongo_db = MongoDBManager.get_db()
        sender_id_int = int(req.sender_id) if str(req.sender_id).isdigit() else None
        query_id = {"$in": [req.sender_id, sender_id_int]} if sender_id_int is not None else req.sender_id
        
        # Check if conversation exists
        conv = await mongo_db.conversations.find_one({
            "platform": req.platform.lower(),
            "user.sender_id": query_id
        })
        if not conv:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Conversation not found in MongoDB."
            )
            
        if str(conv.get("organization_id", "")) != str(current_user["organization_id"]):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have access to this conversation."
            )
            
        # Update flag
        bot_id = "ai" if req.ai_assigned else None
        await mongo_db.conversations.update_one(
            {
                "platform": req.platform.lower(),
                "user.sender_id": query_id
            },
            {
                "$set": {
                    "ai_assigned": req.ai_assigned,
                    "bot_id": bot_id,
                    "updated_at": datetime.now(timezone.utc)
                }
            }
        )
        
        conversation_id = str(conv["_id"])
        org_id = str(conv.get("organization_id", current_user["organization_id"]))
        locker_name = "AI" if req.ai_assigned else None

        # Handle Redis lock
        if req.ai_assigned:
            try:
                await ChatLockManager.release_lock(org_id, conversation_id)
            except Exception as lock_err:
                logger.warning(f"Failed to release Redis lock on toggle-ai: {lock_err}")
        else:
            # AI auto-reply turned off, try to lock to the user if they have an active websocket
            socket_id = manager.find_socket_id(current_user["user_id"], req.platform, str(req.sender_id))
            if socket_id:
                try:
                    # Resolve full name using a new session
                    async with SessionLocal() as local_session:
                        locker_name = await get_user_name_by_id(local_session, current_user["user_id"])
                    await ChatLockManager.acquire_lock(
                        org_id=org_id,
                        conversation_id=conversation_id,
                        user_id=current_user["user_id"],
                        socket_id=socket_id,
                        user_name=locker_name
                    )
                    # Also update MongoDB bot_id to current_user
                    bot_id = current_user["user_id"]
                    await mongo_db.conversations.update_one(
                        {"_id": conv["_id"]},
                        {"$set": {"bot_id": bot_id}}
                    )
                except Exception as lock_err:
                    logger.warning(f"Failed to acquire Redis lock on toggle-ai: {lock_err}")

        # Broadcast the lock status update to WebSocket clients
        try:
            ws_event = {
                "org_id": org_id,
                "platform": req.platform.lower(),
                "sender_id": req.sender_id,
                "type": "chat_lock_update",
                "bot_id": bot_id,
                "locker_name": locker_name
            }
            await manager.broadcast(org_id, ws_event)
        except Exception as ws_err:
            logger.error(f"Failed to broadcast lock update from toggle-ai: {ws_err}")
            
        return {"success": True, "ai_assigned": req.ai_assigned}
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to toggle AI assignment: {str(e)}"
        )


@router.post("/lock")
async def lock_chat(
    req: LockChatRequest,
    db_session: AsyncSession = Depends(get_db),
    current_user: dict = Depends(check_permission("chats"))
):
    try:
        mongo_db = MongoDBManager.get_db()
        sender_id_int = int(req.sender_id) if str(req.sender_id).isdigit() else None
        query_id = {"$in": [req.sender_id, sender_id_int]} if sender_id_int is not None else req.sender_id

        # Verify access rights
        has_access = await check_chat_access(req.platform, req.sender_id, current_user["user_id"], db_session)
        if not has_access:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You are not authorized to access this chat."
            )

        conv = await mongo_db.conversations.find_one({
            "platform": req.platform.lower(),
            "user.sender_id": query_id
        })
        if not conv:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Conversation not found."
            )

        # Access check: non-owners can only lock the conversation to themselves (or unlock if they hold it)
        role = current_user.get("role", "").upper()
        current_bot_id = conv.get("bot_id")
        
        # If trying to lock to someone else and user is not OWNER
        if req.bot_id and req.bot_id != "ai" and req.bot_id != current_user["user_id"] and role != "OWNER":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only lock the conversation to yourself."
            )

        # If chat is currently locked by someone else, and current user is not OWNER
        if current_bot_id and current_bot_id != "ai" and current_bot_id != current_user["user_id"] and role != "OWNER":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="This conversation is locked by another agent."
            )

        # Synchronize ai_assigned flag based on bot_id
        ai_assigned = True if req.bot_id == "ai" else False

        # Resolve locker's full name
        locker_name = None
        if req.bot_id == "ai":
            locker_name = "AI"
        elif req.bot_id:
            locker_name = await get_user_name_by_id(db_session, req.bot_id)

        # Update MongoDB
        await mongo_db.conversations.update_one(
            {
                "platform": req.platform.lower(),
                "user.sender_id": query_id
            },
            {
                "$set": {
                    "bot_id": req.bot_id,
                    "ai_assigned": ai_assigned,
                    "updated_at": datetime.now(timezone.utc)
                }
            }
        )

        conversation_id = str(conv["_id"])
        org_id = str(conv.get("organization_id", current_user["organization_id"]))

        # Acquire/release Redis lock
        if req.bot_id and req.bot_id != "ai":
            try:
                socket_id = manager.find_socket_id(req.bot_id, req.platform, str(req.sender_id)) or f"lock-{uuid4()}"
                await ChatLockManager.acquire_lock(
                    org_id=org_id,
                    conversation_id=conversation_id,
                    user_id=req.bot_id,
                    socket_id=socket_id,
                    user_name=locker_name
                )
            except Exception as lock_err:
                logger.warning(f"Failed to acquire Redis lock in lock_chat endpoint: {lock_err}")
        else:
            try:
                await ChatLockManager.release_lock(org_id, conversation_id)
            except Exception as lock_err:
                logger.warning(f"Failed to release Redis lock in lock_chat endpoint: {lock_err}")

        # Broadcast the lock status update to WebSocket clients
        try:
            ws_event = {
                "org_id": org_id,
                "platform": req.platform.lower(),
                "sender_id": req.sender_id,
                "type": "chat_lock_update",
                "bot_id": req.bot_id,
                "locker_name": locker_name
            }
            await manager.broadcast(org_id, ws_event)
        except Exception as ws_err:
            logger.error(f"Failed to broadcast chat_lock_update: {ws_err}")

        return {"success": True, "bot_id": req.bot_id, "locker_name": locker_name}
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to lock conversation: {str(e)}"
        )

class MarkReadRequest(BaseModel):
    sender_id: Union[int, str]
    platform: str

@router.post("/read")
async def mark_chat_as_read(
    req: MarkReadRequest,
    db_session: AsyncSession = Depends(get_db),
    current_user: dict = Depends(check_permission("chats"))
):
    """
    Mark all inbound messages in a conversation as seen in MongoDB.
    If the platform is Instagram, trigger the 'mark_seen' action to the Instagram Graph API.
    Broadcasts the seen/read status update via WebSocket.
    """
    try:
        # Verify access rights
        has_access = await check_chat_access(req.platform, req.sender_id, current_user["user_id"], db_session)
        if not has_access:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You are not authorized to access this chat."
            )

        mongo_db = MongoDBManager.get_db()
        sender_id_int = int(req.sender_id) if str(req.sender_id).isdigit() else None
        query_id = {"$in": [req.sender_id, sender_id_int]} if sender_id_int is not None else req.sender_id
        
        # Check if conversation exists
        conv = await mongo_db.conversations.find_one({
            "platform": req.platform.lower(),
            "user.sender_id": query_id
        })
        if not conv:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Conversation not found in MongoDB."
            )

        org_id = conv.get("organization_id")
        actual_sender_id = conv["user"]["sender_id"]

        # Update all inbound messages inside the conversation to seen = True
        messages = conv.get("messages", [])
        updated = False
        for msg in messages:
            if msg.get("direction") == "inbound" and not msg.get("seen"):
                msg["seen"] = True
                updated = True

        if updated:
            await mongo_db.conversations.update_one(
                {
                    "platform": req.platform.lower(),
                    "user.sender_id": actual_sender_id
                },
                {
                    "$set": {
                        "messages": messages,
                        "updated_at": datetime.now(timezone.utc)
                    }
                }
            )

        # Broadcast the status update to WebSocket clients
        try:
            ws_event = {
                "org_id": str(org_id),
                "platform": req.platform.lower(),
                "sender_id": actual_sender_id,
                "type": "chat_read_update",
                "seen": True
            }
            await manager.broadcast(str(org_id), ws_event)
        except Exception as ws_err:
            logger.error(f"Failed to broadcast chat_read_update: {ws_err}")

        # If Instagram, trigger 'mark_seen' Graph API call
        if req.platform.lower() == "instagram":
            # Look up the connector in PostgreSQL to get the access token
            stmt = select(PlatformConnector).where(
                PlatformConnector.platform == "instagram"
            )
            result = await db_session.execute(stmt)
            connectors = result.scalars().all()
            
            connector = None
            for c in connectors:
                if str(c.business_id) == str(org_id):
                    connector = c
                    break
                    
            if connector:
                bot_token = None
                if connector.tokens.get("access_token_encrypted"):
                    from shared.utils import decrypt_access_token
                    from shared.config import JWT_SECRET
                    try:
                        bot_token = decrypt_access_token(
                            connector.tokens["token_iv"],
                            connector.tokens["token_ciphertext"],
                            connector.tokens["token_auth_tag"],
                            str(JWT_SECRET)
                        )
                    except Exception as e:
                        logger.error(f"Failed to decrypt Instagram access token for mark_seen: {e}")
                else:
                    bot_token = connector.tokens.get("access_token")

                if bot_token:
                    ig_account_id = connector.platform_account_id
                    instagram_endpoint = f"https://graph.instagram.com/v25.0/{ig_account_id}/messages"
                    try:
                        import httpx
                        async with httpx.AsyncClient() as client:
                            payload = {
                                "recipient": {"id": str(req.sender_id)},
                                "sender_action": "mark_seen"
                            }
                            logger.info(f"Sending mark_seen to Instagram Graph API for user {req.sender_id}")
                            resp = await client.post(instagram_endpoint, json=payload, params={"access_token": bot_token}, timeout=5.0)
                            if resp.status_code == 200:
                                logger.debug("Successfully marked messages as seen on Instagram.")
                            else:
                                logger.error(f"Failed to send mark_seen to Instagram: {resp.status_code} - {resp.text}")
                    except Exception as e:
                        logger.error(f"Network error sending mark_seen to Instagram: {str(e)}")

        return {"success": True}
        
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to mark chat as read: {str(e)}"
        )

# ================= Handoff Endpoints =================

@router.post("/handoff/request")
async def request_handoff_endpoint(
    req: HandoffRequestModel,
    db_session: AsyncSession = Depends(get_db),
    current_user: dict = Depends(check_permission("chats"))
):
    """
    Request to take over a customer conversation that is currently locked by another team member.
    Sends a DM to the current handler with accept/decline options.
    """
    try:
        # Find the conversation
        mongo_db = MongoDBManager.get_db()
        sender_id_int = int(req.sender_id) if str(req.sender_id).isdigit() else None
        query_id = {"$in": [str(req.sender_id), sender_id_int]} if sender_id_int is not None else str(req.sender_id)
        conv = await mongo_db.conversations.find_one({
            "platform": req.platform.lower(),
            "user.sender_id": query_id
        })
        if not conv:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Conversation not found."
            )

        conversation_id = str(conv["_id"])
        org_id = str(conv.get("organization_id", current_user["organization_id"]))
        handler_id = conv.get("bot_id")

        if not handler_id or handler_id == "ai":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This conversation is not currently handled by a team member."
            )

        if handler_id == current_user["user_id"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="You are already handling this conversation."
            )

        # Get requester name
        requester_name = await get_user_name_by_id(db_session, current_user["user_id"]) or "A team member"

        result = await ChatHandoffService.request_handoff(
            conversation_id=conversation_id,
            requester_id=current_user["user_id"],
            requester_name=requester_name,
            handler_id=handler_id,
            org_id=org_id
        )

        return {"success": True, "handoff": result}

    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create handoff request: {str(e)}"
        )

@router.post("/handoff/respond")
async def respond_handoff_endpoint(
    req: HandoffRespondModel,
    db_session: AsyncSession = Depends(get_db),
    current_user: dict = Depends(check_permission("chats"))
):
    """
    Accept or decline a handoff request. Only the current handler can respond.
    """
    try:
        org_id = current_user["organization_id"]
        handler_id = current_user["user_id"]
        handler_name = await get_user_name_by_id(db_session, handler_id) or "Unknown"

        if req.action == "grant":
            # Find an active socket for the handler to pass to grant
            socket_id = f"handoff-{uuid4()}"  # Placeholder socket for grant flow
            result = await ChatHandoffService.grant_handoff(
                handoff_id=req.handoff_id,
                org_id=org_id,
                handler_id=handler_id,
                handler_name=handler_name,
                handler_socket_id=socket_id
            )
        elif req.action == "decline":
            result = await ChatHandoffService.decline_handoff(
                handoff_id=req.handoff_id,
                org_id=org_id,
                handler_id=handler_id
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Action must be 'grant' or 'decline'."
            )

        if result.get("error"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result["error"]
            )

        return {"success": True, **result}

    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process handoff response: {str(e)}"
        )

# ================= WebSocket Support =================

import asyncio
import json
import logging
from fastapi import WebSocket, WebSocketDisconnect
from aiokafka import AIOKafkaConsumer
from shared.config import KAFKA_BOOTSTRAP_SERVERS

logger = logging.getLogger("api_gateway.chats_ws")

async def safe_close(websocket: WebSocket, code: int):
    try:
        from starlette.websockets import WebSocketState
        if websocket.client_state == WebSocketState.CONNECTING:
            await websocket.accept()
        if websocket.client_state == WebSocketState.CONNECTED:
            await websocket.close(code=code)
    except Exception:
        pass

class ConnectionManager:
    def __init__(self):
        self.active_connections: dict[str, list[WebSocket]] = {}
        # Mapping from (platform, sender_id_str) -> user_id
        self.active_chat_sessions: dict[tuple[str, str], str] = {}
        # Mapping from WebSocket -> (platform, sender_id_str, user_id)
        self.websocket_to_chat: dict[WebSocket, tuple[str, str, str]] = {}
        # Mappings for socket IDs
        self.websocket_to_socket_id: dict[WebSocket, str] = {}

    def find_socket_id(self, user_id: str, platform: str, sender_id: str) -> Optional[str]:
        for ws, chat_info in self.websocket_to_chat.items():
            ws_platform, ws_sender_id, ws_user_id = chat_info
            if ws_user_id == user_id and ws_platform == platform.lower() and str(ws_sender_id) == str(sender_id):
                return self.websocket_to_socket_id.get(ws)
        return None

    async def connect(
        self,
        org_id: str,
        websocket: WebSocket,
        user_id: Optional[str] = None,
        platform: Optional[str] = None,
        sender_id: Optional[Union[int, str]] = None,
        db_session: AsyncSession = None,
        socket_id: Optional[str] = None
    ) -> bool:
        try:
            from starlette.websockets import WebSocketState
            if websocket.client_state == WebSocketState.CONNECTING:
                await websocket.accept()
        except Exception:
            return False

        # Generate a socket ID if not provided
        if not socket_id:
            from uuid import uuid4
            socket_id = f"ws-{uuid4()}"

        # Enforce connection restrictions if user_id and chat details are provided
        if user_id and platform and sender_id and db_session:
            sender_id_str = str(sender_id)
            chat_key = (platform.lower(), sender_id_str)
            # Check DB permission first
            has_access = await check_chat_access(platform, sender_id_str, user_id, db_session)
            if not has_access:
                try:
                    await websocket.send_json({
                        "type": "error",
                        "message": "Access denied. Chat is assigned to another user or you lack OWNER role."
                    })
                    await websocket.close(code=4003)
                except Exception:
                    pass
                return False

            self.websocket_to_socket_id[websocket] = socket_id

            # Re-acquire Redis lock on connect/reconnect if already claimed by this user in MongoDB
            mongo_db = MongoDBManager.get_db()
            sender_id_int = int(sender_id_str) if sender_id_str.isdigit() else None
            query_id = {"$in": [sender_id_str, sender_id_int]} if sender_id_int is not None else sender_id_str
            conv = await mongo_db.conversations.find_one({
                "platform": platform.lower(),
                "user.sender_id": query_id
            })
            if conv:
                conv_id = str(conv["_id"])
                bot_id = conv.get("bot_id")
                ai_assigned = conv.get("ai_assigned", False)

                # Sticky re-acquire: if bot_id matches user_id in MongoDB, acquire lock in Redis
                if bot_id == user_id and not ai_assigned:
                    locker_name = await get_user_name_by_id(db_session, user_id)
                    try:
                        await ChatLockManager.acquire_lock(
                            org_id=org_id,
                            conversation_id=conv_id,
                            user_id=user_id,
                            socket_id=socket_id,
                            user_name=locker_name
                        )
                        # Broadcast the lock status update
                        ws_event = {
                            "org_id": org_id,
                            "platform": platform.lower(),
                            "sender_id": sender_id_str,
                            "type": "chat_lock_update",
                            "bot_id": user_id,
                            "locker_name": locker_name
                        }
                        await self.broadcast(org_id, ws_event)
                    except Exception as lock_err:
                        logger.error(f"Failed to acquire Redis lock on connect: {lock_err}")

            self.active_chat_sessions[chat_key] = user_id
            self.websocket_to_chat[websocket] = (platform.lower(), sender_id_str, user_id)

        if org_id not in self.active_connections:
            self.active_connections[org_id] = []
        self.active_connections[org_id].append(websocket)
        logger.info(f"[WebSocket] Connected client for org: {org_id}. Total active: {len(self.active_connections[org_id])}")
        return True

    async def disconnect(self, org_id: str, websocket: WebSocket):
        if org_id in self.active_connections:
            if websocket in self.active_connections[org_id]:
                self.active_connections[org_id].remove(websocket)
            if not self.active_connections[org_id]:
                del self.active_connections[org_id]

        socket_id = self.websocket_to_socket_id.pop(websocket, None)

        if websocket in self.websocket_to_chat:
            platform, sender_id_str, user_id = self.websocket_to_chat.pop(websocket)
            chat_key = (platform, sender_id_str)
            if self.active_chat_sessions.get(chat_key) == user_id:
                self.active_chat_sessions.pop(chat_key, None)

            # Auto-release Redis lock (keeps MongoDB claim sticky for re-acquiring on reconnect)
            if socket_id:
                try:
                    released_locks = await ChatLockManager.release_all_locks_for_socket(socket_id)
                    mongo_db = MongoDBManager.get_db()
                    for lock in released_locks:
                        conv_id = lock["conversation_id"]
                        # Find the conversation to get platform and sender_id
                        from bson import ObjectId
                        try:
                            conv = await mongo_db.conversations.find_one({"_id": ObjectId(conv_id)})
                        except Exception:
                            conv = None

                        if conv:
                            actual_platform = conv["platform"]
                            actual_sender_id = conv["user"]["sender_id"]

                            # Broadcast the lock release in real-time to other clients
                            ws_event = {
                                "org_id": org_id,
                                "platform": actual_platform,
                                "sender_id": str(actual_sender_id),
                                "type": "chat_lock_update",
                                "bot_id": None,
                                "locker_name": None
                            }
                            await self.broadcast(org_id, ws_event)
                except Exception as ws_err:
                    logger.error(f"Failed to auto-release Redis locks on disconnect: {ws_err}")

        logger.info(f"[WebSocket] Disconnected client.")

    async def broadcast(self, org_id: str, message: dict):
        if org_id in self.active_connections:
            for connection in self.active_connections[org_id]:
                try:
                    await connection.send_json(message)
                except Exception as e:
                    logger.warning(f"[WebSocket] Failed to send JSON message: {e}")

manager = ConnectionManager()

@router.websocket("/ws/{org_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    org_id: str,
    user_id: Optional[str] = None,
    platform: Optional[str] = None,
    sender_id: Optional[str] = None
):
    async with SessionLocal() as db_session:
        # Check permissions first
        if not user_id:
            await safe_close(websocket, 4003)
            return
            
        try:
            user_stmt = select(User).where(User.id == UUID(user_id))
            user_result = await db_session.execute(user_stmt)
            db_user = user_result.scalar_one_or_none()
            if not db_user:
                await safe_close(websocket, 4003)
                return
            
            role = db_user.role.value if hasattr(db_user.role, 'value') else str(db_user.role)
            role = role.upper()
            if role != "OWNER":
                from services.api_gateway.routers.auth_routers.me import get_user_permissions
                permissions = await get_user_permissions(db_session, user_id, role)
                if "chats" not in permissions:
                    await safe_close(websocket, 4003)
                    return
        except Exception as e:
            logger.error(f"[WebSocket] Authorization error: {e}")
            await safe_close(websocket, 4003)
            return

        try:
            socket_id = f"ws-{uuid4()}"
            success = await manager.connect(
                org_id=org_id,
                websocket=websocket,
                user_id=user_id,
                platform=platform,
                sender_id=sender_id,
                db_session=db_session,
                socket_id=socket_id
            )
            if not success:
                return
        except WebSocketDisconnect:
            logger.info(f"[WebSocket] Client disconnected during connection handshake.")
            return
        except Exception as e:
            logger.error(f"[WebSocket] Error during connection handshake: {e}")
            try:
                await websocket.close(code=1011)
            except Exception:
                pass
            return

    try:
        while True:
            # Maintain connection alive, listen for disconnects
            await websocket.receive_text()
    except WebSocketDisconnect:
        await manager.disconnect(org_id, websocket)
    except Exception as e:
        logger.error(f"[WebSocket] Connection error for org {org_id}: {e}")
        await manager.disconnect(org_id, websocket)

_ws_consumer_task: Optional[asyncio.Task] = None

async def consume_chat_websocket_events():
    """
    Background worker inside API Gateway to read from chat_websocket Kafka topic
    and broadcast messages to connected websocket clients.
    """
    try:
        bootstrap_servers = [s.strip() for s in KAFKA_BOOTSTRAP_SERVERS.split(",")]
        logger.info(f"[WebSocket Kafka Consumer] Starting on brokers: {bootstrap_servers}")
        
        # Use auto_offset_reset='latest' since websocket clients only care about real-time events while connected.
        from shared.config import KAFKA_SECURITY_PROTOCOL
        kwargs = {
            "bootstrap_servers": bootstrap_servers,
            "group_id": "api-gateway-ws-group",
            "value_deserializer": lambda v: json.loads(v.decode("utf-8")),
            "auto_offset_reset": "latest"
        }
        
        if KAFKA_SECURITY_PROTOCOL == "SASL_SSL":
            from shared.kafka_producer import msk_oauth_callback
            kwargs.update({
                "security_protocol": "SASL_SSL",
                "sasl_mechanism": "OAUTHBEARER",
                "sasl_oauth_token_provider": msk_oauth_callback
            })
            
        consumer = AIOKafkaConsumer(
            "chat_websocket",
            **kwargs
        )
        
        await consumer.start()
        logger.info("[WebSocket Kafka Consumer] Successfully connected and listening on 'chat_websocket'.")
        try:
            while True:
                msg_pack = await consumer.getmany(timeout_ms=1000)
                for tp, messages in msg_pack.items():
                    for msg in messages:
                        event = msg.value
                        org_id = event.get("org_id")
                        if org_id:
                            logger.info(f"[WebSocket Kafka Consumer] Broadcasting event to org: {org_id}")
                            await manager.broadcast(org_id, event)
        finally:
            await consumer.stop()
            logger.info("[WebSocket Kafka Consumer] Stopped.")
    except asyncio.CancelledError:
        logger.info("[WebSocket Kafka Consumer] Task cancelled.")
    except Exception as e:
        logger.error(f"[WebSocket Kafka Consumer] Exception: {e}", exc_info=True)

async def start_ws_kafka_consumer():
    global _ws_consumer_task
    if _ws_consumer_task is None or _ws_consumer_task.done():
        _ws_consumer_task = asyncio.create_task(consume_chat_websocket_events())
        logger.info("[WebSocket Gateway] Started background Kafka ws consumer task.")

async def stop_ws_kafka_consumer():
    global _ws_consumer_task
    if _ws_consumer_task and not _ws_consumer_task.done():
        logger.info("[WebSocket Gateway] Stopping background Kafka ws consumer task...")
        _ws_consumer_task.cancel()
        try:
            await _ws_consumer_task
        except asyncio.CancelledError:
            pass
        _ws_consumer_task = None
