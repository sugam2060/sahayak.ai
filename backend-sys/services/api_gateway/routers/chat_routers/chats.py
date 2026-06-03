from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from typing import Optional, List, Union
from datetime import datetime, timezone
from shared.database.mongodb import MongoDBManager
from sqlalchemy.ext.asyncio import AsyncSession
from shared.database.engine import SessionLocal
from shared.database.schema.platform_connectors import PlatformConnector
from sqlalchemy import select
from pydantic import BaseModel
from services.api_gateway.routers.auth_routers.me import get_current_user
from shared.database.schema.users import User, UserRole
from uuid import UUID
import logging

logger = logging.getLogger("api_gateway.chats")

async def check_chat_access(platform: str, sender_id: Union[int, str], user_id: str, db_session: AsyncSession) -> bool:
    mongo_db = MongoDBManager.get_db()
    sender_id_int = int(sender_id) if str(sender_id).isdigit() else None
    query_id = {"$in": [sender_id, sender_id_int]} if sender_id_int is not None else sender_id
    
    conv = await mongo_db.conversations.find_one({
        "platform": platform.lower(),
        "user.sender_id": query_id
    })
    if not conv:
        # If no conversation exists yet, verify they are at least a valid user
        user_stmt = select(User).where(User.id == UUID(user_id))
        user_result = await db_session.execute(user_stmt)
        return user_result.scalar_one_or_none() is not None

    assigned_user = conv.get("assigned_user")
    user_stmt = select(User).where(User.id == UUID(user_id))
    user_result = await db_session.execute(user_stmt)
    db_user = user_result.scalar_one_or_none()
    if not db_user:
        return False

    if assigned_user:
        return str(assigned_user) == str(user_id)
    else:
        return db_user.role == UserRole.OWNER or db_user.role.value == "OWNER"


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

@router.get("")
async def get_chat_list(organization_id: Optional[str] = None):
    """
    Get all conversations/chats, optionally filtered by organization_id.
    """
    try:
        db = MongoDBManager.get_db()
        query = {}
        if organization_id:
            query["organization_id"] = organization_id
            
        # Retrieve all conversations, sorted by updated_at descending
        cursor = db.conversations.find(query).sort("updated_at", -1)
        chats = []
        async for doc in cursor:
            # Convert ObjectId to string for JSON serialization
            doc["_id"] = str(doc["_id"])
            chats.append(doc)
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
    current_user: dict = Depends(get_current_user),
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
    current_user: dict = Depends(get_current_user)
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

        # 1. Retrieve conversation from MongoDB to get organization_id, bot_name, and chat_id
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
        bot_name = conv.get("bot_name")
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
            ig_account_id=connector.platform_account_id if req.platform.lower() == "instagram" else None
        )
        
        return {"success": True, "message": "Reply event successfully sent to Kafka."}
        
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to send reply: {str(e)}"
        )

@router.post("/reply-image")
async def send_chat_reply_image(
    sender_id: str = Form(...),
    platform: str = Form(...),
    image_file: Optional[UploadFile] = File(None),
    image_files: Optional[List[UploadFile]] = File(None),
    db_session: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
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

        # 1. Retrieve conversation from MongoDB to get organization_id, bot_name, and chat_id
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
        bot_name = conv.get("bot_name")
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
                ig_account_id=connector.platform_account_id if platform.lower() == "instagram" else None
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
    current_user: dict = Depends(get_current_user),
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
async def toggle_ai_assigned(req: ToggleAIAssignedRequest):
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
            
        # Update flag
        await mongo_db.conversations.update_one(
            {
                "platform": req.platform.lower(),
                "user.sender_id": query_id
            },
            {
                "$set": {
                    "ai_assigned": req.ai_assigned,
                    "updated_at": datetime.now(timezone.utc)
                }
            }
        )
        

        
        # Broadcast the status update to WebSocket clients so the frontend state updates in real-time
        try:
            ws_event = {
                "org_id": conv.get("organization_id"),
                "platform": req.platform.lower(),
                "sender_id": req.sender_id,
                "type": "ai_assigned_toggle",
                "ai_assigned": req.ai_assigned
            }
            # We broadcast it directly since api_gateway is hosting the WebSocket connections
            await manager.broadcast(conv.get("organization_id"), ws_event)
        except Exception as ws_err:
            logger.error(f"Failed to broadcast ai_assigned_toggle: {ws_err}")
            
        return {"success": True, "ai_assigned": req.ai_assigned}
        
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to toggle AI assignment: {str(e)}"
        )

# ================= WebSocket Support =================

import asyncio
import json
import logging
from fastapi import WebSocket, WebSocketDisconnect
from aiokafka import AIOKafkaConsumer
from shared.config import KAFKA_BOOTSTRAP_SERVERS

logger = logging.getLogger("api_gateway.chats_ws")

class ConnectionManager:
    def __init__(self):
        self.active_connections: dict[str, list[WebSocket]] = {}
        # Mapping from (platform, sender_id_str) -> user_id
        self.active_chat_sessions: dict[tuple[str, str], str] = {}
        # Mapping from WebSocket -> (platform, sender_id_str, user_id)
        self.websocket_to_chat: dict[WebSocket, tuple[str, str, str]] = {}

    async def connect(
        self,
        org_id: str,
        websocket: WebSocket,
        user_id: Optional[str] = None,
        platform: Optional[str] = None,
        sender_id: Optional[Union[int, str]] = None,
        db_session: AsyncSession = None
    ) -> bool:
        await websocket.accept()

        # Enforce connection restrictions if user_id and chat details are provided
        if user_id and platform and sender_id and db_session:
            sender_id_str = str(sender_id)
            # Check DB permission first
            has_access = await check_chat_access(platform, sender_id_str, user_id, db_session)
            if not has_access:
                await websocket.send_json({
                    "type": "error",
                    "message": "Access denied. Chat is assigned to another user or you lack OWNER role."
                })
                await websocket.close(code=4003)
                return False

            # Check for concurrent user-2 connection to same chat
            chat_key = (platform.lower(), sender_id_str)
            if chat_key in self.active_chat_sessions:
                existing_user = self.active_chat_sessions[chat_key]
                if str(existing_user) != str(user_id):
                    await websocket.send_json({
                        "type": "error",
                        "message": "Another user is currently connected to this chat."
                    })
                    await websocket.close(code=4009)
                    return False

            self.active_chat_sessions[chat_key] = user_id
            self.websocket_to_chat[websocket] = (platform.lower(), sender_id_str, user_id)

        if org_id not in self.active_connections:
            self.active_connections[org_id] = []
        self.active_connections[org_id].append(websocket)
        logger.info(f"[WebSocket] Connected client for org: {org_id}. Total active: {len(self.active_connections[org_id])}")
        return True

    def disconnect(self, org_id: str, websocket: WebSocket):
        if org_id in self.active_connections:
            if websocket in self.active_connections[org_id]:
                self.active_connections[org_id].remove(websocket)
            if not self.active_connections[org_id]:
                del self.active_connections[org_id]

        if websocket in self.websocket_to_chat:
            platform, sender_id_str, user_id = self.websocket_to_chat.pop(websocket)
            chat_key = (platform, sender_id_str)
            if self.active_chat_sessions.get(chat_key) == user_id:
                self.active_chat_sessions.pop(chat_key, None)

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
        success = await manager.connect(
            org_id=org_id,
            websocket=websocket,
            user_id=user_id,
            platform=platform,
            sender_id=sender_id,
            db_session=db_session
        )
        if not success:
            return

    try:
        while True:
            # Maintain connection alive, listen for disconnects
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(org_id, websocket)
    except Exception as e:
        logger.error(f"[WebSocket] Connection error for org {org_id}: {e}")
        manager.disconnect(org_id, websocket)

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
