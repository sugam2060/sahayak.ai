from fastapi import APIRouter, Depends, HTTPException, status, WebSocket, Query
from starlette.websockets import WebSocketDisconnect
from typing import Optional, List, Union
from datetime import datetime, timezone
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel

from shared.utils import get_db
from shared.database.engine import SessionLocal
from shared.database.schema.users import User
from shared.database.mongodb import MongoDBManager
from shared.kafka_producer import KafkaProducerPool
from services.api_gateway.routers.auth_routers.me import get_current_user, get_user_permissions
from services.api_gateway.routers.teams.permissions import check_permission

# Submodule classes
from .manager import manager
import importlib
_service_module = importlib.import_module("services.chatai-service.internal_chat.service")
InternalChatService = _service_module.InternalChatService

router = APIRouter(prefix="/api/internal-chats", tags=["Internal Chat"])

db_service = InternalChatService()

class CreateGroupRequest(BaseModel):
    name: str
    member_ids: List[str]

class ManageGroupMembersRequest(BaseModel):
    action: str  # "add" or "remove"
    user_id: str

class RespondCustomerRequest(BaseModel):
    message_id: str
    action: str  # "accept" or "decline"

async def get_user_name_by_id(db_session: AsyncSession, user_id_str: str) -> Optional[str]:
    try:
        user_uuid = UUID(user_id_str)
        stmt = select(User).where(User.id == user_uuid)
        result = await db_session.execute(stmt)
        db_user = result.scalar_one_or_none()
        return db_user.full_name if db_user else None
    except Exception:
        return None

@router.get("/members")
async def list_members(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """List other active organization members."""
    org_id = UUID(current_user["organization_id"])
    curr_user_id = UUID(current_user["user_id"])
    
    stmt = select(User.id, User.full_name, User.role, User.email).where(
        User.organization_id == org_id,
        User.id != curr_user_id,
        User.is_active == True
    )
    result = await db.execute(stmt)
    members = []
    for uid, name, role, email in result.all():
        role_val = role.value if hasattr(role, 'value') else str(role)
        members.append({
            "user_id": str(uid),
            "full_name": name,
            "role": role_val,
            "email": email
        })
    return {"success": True, "members": members}

@router.get("/direct/history/{target_user_id}")
async def direct_history(
    target_user_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Fetch 1:1 direct chat history between current user and target user."""
    # Verify target user exists in organization
    try:
        target_uuid = UUID(target_user_id)
        stmt = select(User).where(User.id == target_uuid, User.organization_id == UUID(current_user["organization_id"]))
        result = await db.execute(stmt)
        if not result.scalar_one_or_none():
            raise HTTPException(status_code=404, detail="Recipient not found in your organization.")
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid target user ID.")
        
    convo = await db_service.get_or_create_direct_conversation(
        current_user["organization_id"],
        current_user["user_id"],
        target_user_id
    )
    return {"success": True, "conversation": convo}

@router.get("/groups")
async def list_groups(
    current_user: dict = Depends(get_current_user)
):
    """List all group chats the current user belongs to."""
    mongo_db = MongoDBManager.get_db()
    cursor = mongo_db.internal_conversations.find({
        "organization_id": current_user["organization_id"],
        "type": "group",
        "user_ids": current_user["user_id"]
    }).sort("updated_at", -1)
    
    groups = []
    async for doc in cursor:
        doc["_id"] = str(doc["_id"])
        groups.append(doc)
    return {"success": True, "groups": groups}

@router.post("/groups")
async def create_group(
    req: CreateGroupRequest,
    current_user: dict = Depends(check_permission("teams"))
):
    """Create a new team-scoped group chat."""
    org_id = current_user["organization_id"]
    admin_id = current_user["user_id"]
    
    convo = await db_service.create_group_conversation(
        org_id,
        req.name,
        admin_id,
        req.member_ids
    )
    
    # Notify connected members via WebSocket
    ws_payload = {
        "org_id": org_id,
        "type": "group",
        "convo_id": convo["_id"],
        "user_ids": convo["user_ids"],
        "event_type": "group_created",
        "conversation": convo
    }
    await KafkaProducerPool.send_message("internal_chat_websocket", ws_payload)
    return {"success": True, "group": convo}

@router.get("/groups/{group_id}/history")
async def group_history(
    group_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Fetch message history for the group (enforces membership)."""
    convo = await db_service.get_group_conversation(group_id)
    if not convo:
        raise HTTPException(status_code=404, detail="Group conversation not found.")
        
    if current_user["user_id"] not in convo["user_ids"]:
        raise HTTPException(status_code=403, detail="You are not a member of this group.")
        
    return {"success": True, "conversation": convo}

@router.delete("/groups/{group_id}")
async def delete_group(
    group_id: str,
    current_user: dict = Depends(check_permission("teams"))
):
    """Delete a group chat (admin-only)."""
    convo = await db_service.get_group_conversation(group_id)
    if not convo:
        raise HTTPException(status_code=404, detail="Group conversation not found.")
        
    # Enforce admin rights
    if current_user["user_id"] not in convo.get("group_admin_ids", []):
        raise HTTPException(status_code=403, detail="Only group admins can delete this group.")
        
    success = await db_service.delete_group_conversation(group_id)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to delete the group.")
        
    # Notify connected members via WebSocket
    ws_payload = {
        "org_id": current_user["organization_id"],
        "type": "group",
        "convo_id": group_id,
        "user_ids": convo["user_ids"],
        "event_type": "group_deleted",
        "conversation": convo
    }
    await KafkaProducerPool.send_message("internal_chat_websocket", ws_payload)
    return {"success": True}

@router.post("/groups/{group_id}/members")
async def manage_group_members(
    group_id: str,
    req: ManageGroupMembersRequest,
    current_user: dict = Depends(get_current_user)
):
    """Add or remove members from a group chat (admin-only)."""
    convo = await db_service.get_group_conversation(group_id)
    if not convo:
        raise HTTPException(status_code=404, detail="Group conversation not found.")
        
    if current_user["user_id"] not in convo["group_admin_ids"]:
        raise HTTPException(status_code=403, detail="Only group admins can manage members.")
        
    now = datetime.now(timezone.utc)
    mongo_db = MongoDBManager.get_db()
    
    if req.action == "add":
        if req.user_id not in convo["user_ids"]:
            convo["user_ids"].append(req.user_id)
            await mongo_db.internal_conversations.update_one(
                {"_id": group_id},
                {
                    "$push": {"user_ids": req.user_id},
                    "$set": {"updated_at": now}
                }
            )
    elif req.action == "remove":
        if req.user_id in convo["user_ids"]:
            convo["user_ids"].remove(req.user_id)
            # Also remove from admins if they were one
            admin_pull = {}
            if req.user_id in convo["group_admin_ids"]:
                convo["group_admin_ids"].remove(req.user_id)
                admin_pull = {"group_admin_ids": req.user_id}
                
            await mongo_db.internal_conversations.update_one(
                {"_id": group_id},
                {
                    "$pull": {
                        "user_ids": req.user_id,
                        **admin_pull
                    },
                    "$set": {"updated_at": now}
                }
            )
            
    # Notify the updated user membership list
    ws_payload = {
        "org_id": current_user["organization_id"],
        "type": "group",
        "convo_id": group_id,
        "user_ids": convo["user_ids"] + [req.user_id], # notify removed user too so they can update UI
        "event_type": "group_members_updated",
        "group_name": convo["group_name"],
        "member_ids": convo["user_ids"]
    }
    await KafkaProducerPool.send_message("internal_chat_websocket", ws_payload)
    return {"success": True, "user_ids": convo["user_ids"]}

@router.get("/org/history")
async def org_history(
    current_user: dict = Depends(get_current_user)
):
    """Fetch organization broadcast channel history."""
    convo = await db_service.get_or_create_org_conversation(current_user["organization_id"])
    return {"success": True, "conversation": convo}

@router.post("/customer-request/respond")
async def respond_customer_request(
    req: RespondCustomerRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Handle User B accepting/declining a customer join request from User A."""
    mongo_db = MongoDBManager.get_db()
    
    # 1. Locate direct chat containing message_id, where current user is a participant
    convo = await mongo_db.internal_conversations.find_one({
        "type": "direct",
        "user_ids": current_user["user_id"],
        "messages.message_id": req.message_id
    })
    
    if not convo:
        raise HTTPException(status_code=404, detail="Request message not found or unauthorized access.")
        
    # Locate the message object
    req_message = None
    for msg in convo["messages"]:
        if msg["message_id"] == req.message_id:
            req_message = msg
            break
            
    if not req_message or req_message["message_type"] != "customer_chat_request":
        raise HTTPException(status_code=400, detail="Invalid message type. Not a customer request.")
        
    request_data = req_message["customer_chat_request"]
    if request_data["status"] != "pending":
        raise HTTPException(status_code=400, detail=f"Request is already processed: status is '{request_data['status']}'")

    user_a_id = req_message["sender_id"] # Requested user ID
    platform = request_data["platform"]
    sender_id = request_data["sender_id"] # Customer sender ID
    
    action_status = "accepted" if req.action == "accept" else "declined"
    
    # 2. Update status in direct conversation
    updated_convo = await db_service.respond_to_customer_request(req.message_id, action_status)
    
    if req.action == "accept":
        # 3. Handle Customer Thread Unlock and Lock Transfer
        customer_convo = await mongo_db.conversations.find_one({
            "platform": platform.lower(),
            "user.sender_id": {"$in": [sender_id, int(sender_id) if sender_id.isdigit() else None]}
        })
        if not customer_convo:
            raise HTTPException(status_code=404, detail="Customer conversation not found in database.")
            
        # Add User A to allowed_users
        allowed = customer_convo.get("allowed_users", [])
        if user_a_id not in allowed:
            allowed.append(user_a_id)
            
        # Release User B's lock (set bot_id to None or User A if User A is currently connected)
        from services.api_gateway.routers.chat_routers.chats import manager as chats_ws_manager
        
        target_lock_id = None
        user_a_connected = chats_ws_manager.active_chat_sessions.get((platform.lower(), str(sender_id))) == user_a_id
        if user_a_connected:
            target_lock_id = user_a_id
            
        await mongo_db.conversations.update_one(
            {
                "platform": platform.lower(),
                "user.sender_id": {"$in": [sender_id, int(sender_id) if sender_id.isdigit() else None]}
            },
            {
                "$set": {
                    "bot_id": target_lock_id,
                    "allowed_users": allowed,
                    "updated_at": datetime.now(timezone.utc)
                }
            }
        )
        
        # 4. Broadcast chat_lock_update to customer WS clients
        try:
            locker_name = await get_user_name_by_id(db, target_lock_id) if target_lock_id else None
            ws_event = {
                "org_id": current_user["organization_id"],
                "platform": platform.lower(),
                "sender_id": sender_id,
                "type": "chat_lock_update",
                "bot_id": target_lock_id,
                "locker_name": locker_name
            }
            await chats_ws_manager.broadcast(current_user["organization_id"], ws_event)
        except Exception as ws_err:
            print(f"Failed to broadcast lock update on accept request: {ws_err}")

    # 5. Broadcast request status update in DM room
    ws_payload = {
        "org_id": current_user["organization_id"],
        "type": "direct",
        "convo_id": convo["_id"],
        "user_ids": convo["user_ids"],
        "event_type": "request_status_updated",
        "message_id": req.message_id,
        "status": action_status
    }
    await KafkaProducerPool.send_message("internal_chat_websocket", ws_payload)
    
    return {"success": True, "status": action_status}

@router.websocket("/ws/{org_id}")
async def websocket_internal_endpoint(
    websocket: WebSocket,
    org_id: str,
    user_id: Optional[str] = None
):
    async with SessionLocal() as db_session:
        if not user_id:
            try:
                await websocket.close(code=4003)
            except Exception:
                pass
            return
            
        # Authenticate user membership
        try:
            user_stmt = select(User).where(User.id == UUID(user_id), User.organization_id == UUID(org_id))
            user_result = await db_session.execute(user_stmt)
            db_user = user_result.scalar_one_or_none()
            if not db_user:
                try:
                    await websocket.close(code=4003)
                except Exception:
                    pass
                return
        except Exception:
            try:
                await websocket.close(code=4003)
            except Exception:
                pass
            return

        success = await manager.connect(org_id, user_id, websocket)
        if not success:
            return

    try:
        while True:
            # Expect client to send JSON message
            data = await websocket.receive_json()
            chat_type = data.get("type") # "direct", "group", "org"
            text = data.get("text", "")
            msg_type = data.get("message_type", "text")
            
            # Authorization permission guard for request join
            if msg_type == "customer_chat_request":
                # Check permission list
                role_str = db_user.role.value if hasattr(db_user.role, 'value') else str(db_user.role)
                role_str = role_str.upper()
                permissions = await get_user_permissions(db_session, user_id, role_str)
                if "internal_chat:request_customer" not in permissions and role_str != "OWNER":
                    await websocket.send_json({
                        "type": "error",
                        "message": "Access denied. You do not have permission to request access to customer chats."
                    })
                    continue

            # Publish event to correct Kafka topic
            if chat_type == "direct":
                recipient_id = data.get("recipient_id")
                if recipient_id:
                    kafka_payload = {
                        "org_id": org_id,
                        "sender_id": user_id,
                        "sender_name": db_user.full_name,
                        "recipient_id": recipient_id,
                        "text": text,
                        "message_type": msg_type,
                        "customer_chat_request": data.get("customer_chat_request")
                    }
                    await KafkaProducerPool.send_message("internal_chat.direct", kafka_payload)
            elif chat_type == "group":
                group_id = data.get("group_id")
                if group_id:
                    kafka_payload = {
                        "org_id": org_id,
                        "sender_id": user_id,
                        "sender_name": db_user.full_name,
                        "group_id": group_id,
                        "text": text,
                        "message_type": msg_type
                    }
                    await KafkaProducerPool.send_message("internal_chat.group", kafka_payload)
            elif chat_type == "org":
                # Enforce write role permission
                role_str = db_user.role.value if hasattr(db_user.role, 'value') else str(db_user.role)
                if role_str.upper() not in ("OWNER", "ADMIN"):
                    await websocket.send_json({
                        "type": "error",
                        "message": "Access denied. Only Owners and Admins can broadcast in this channel."
                    })
                    continue
                    
                kafka_payload = {
                    "org_id": org_id,
                    "sender_id": user_id,
                    "sender_name": db_user.full_name,
                    "text": text,
                    "message_type": msg_type
                }
                await KafkaProducerPool.send_message("internal_chat.org", kafka_payload)
    except WebSocketDisconnect:
        manager.disconnect(org_id, websocket)
    except Exception as e:
        print(f"[Internal WS] Error: {e}")
        manager.disconnect(org_id, websocket)
