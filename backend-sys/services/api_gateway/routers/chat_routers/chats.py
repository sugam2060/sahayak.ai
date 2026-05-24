from fastapi import APIRouter, Depends, HTTPException, status
from typing import Optional
from shared.database.mongodb import MongoDBManager
from sqlalchemy.ext.asyncio import AsyncSession
from shared.database.engine import SessionLocal
from shared.database.schema.platform_connectors import PlatformConnector
from sqlalchemy import select
from pydantic import BaseModel

router = APIRouter(prefix="/api/chats", tags=["Chat Management"])

async def get_db():
    async with SessionLocal() as session:
        yield session

class SendReplyRequest(BaseModel):
    sender_id: int
    platform: str
    text: str

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
async def get_chat_history(platform: str, sender_id: int):
    """
    Get the full message history for a specific conversation by platform and sender_id.
    """
    try:
        db = MongoDBManager.get_db()
        doc = await db.conversations.find_one({
            "platform": platform.lower(),
            "user.sender_id": sender_id
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
    db_session: AsyncSession = Depends(get_db)
):
    """
    Send a reply to a conversation. Finds the bot token, organization ID, and chat ID
    and publishes the outbound message event to the Kafka topic.
    """
    try:
        # 1. Retrieve conversation from MongoDB to get organization_id, bot_name, and chat_id
        mongo_db = MongoDBManager.get_db()
        conv = await mongo_db.conversations.find_one({
            "platform": req.platform.lower(),
            "user.sender_id": req.sender_id
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
            
        bot_token = connector.tokens.get("bot_token")
        if not bot_token:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Connector is missing the bot token configuration."
            )
            
        # 3. Publish to Kafka 'chat_service' topic
        from services.workers.chat_service import route_outbound_reply
        await route_outbound_reply(
            org_id=str(org_id),
            bot_name=bot_name,
            bot_token=bot_token,
            platform=req.platform.lower(),
            chat_id=chat_id,
            sender_id=req.sender_id,
            text=req.text
        )
        
        return {"success": True, "message": "Reply event successfully sent to Kafka."}
        
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to send reply: {str(e)}"
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

    async def connect(self, org_id: str, websocket: WebSocket):
        await websocket.accept()
        if org_id not in self.active_connections:
            self.active_connections[org_id] = []
        self.active_connections[org_id].append(websocket)
        logger.info(f"[WebSocket] Connected client for org: {org_id}. Total active: {len(self.active_connections[org_id])}")

    def disconnect(self, org_id: str, websocket: WebSocket):
        if org_id in self.active_connections:
            if websocket in self.active_connections[org_id]:
                self.active_connections[org_id].remove(websocket)
            if not self.active_connections[org_id]:
                del self.active_connections[org_id]
        logger.info(f"[WebSocket] Disconnected client for org: {org_id}")

    async def broadcast(self, org_id: str, message: dict):
        if org_id in self.active_connections:
            for connection in self.active_connections[org_id]:
                try:
                    await connection.send_json(message)
                except Exception as e:
                    logger.warning(f"[WebSocket] Failed to send JSON message: {e}")

manager = ConnectionManager()

@router.websocket("/ws/{org_id}")
async def websocket_endpoint(websocket: WebSocket, org_id: str):
    await manager.connect(org_id, websocket)
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
        consumer = AIOKafkaConsumer(
            "chat_websocket",
            bootstrap_servers=bootstrap_servers,
            group_id="api-gateway-ws-group",
            value_deserializer=lambda v: json.loads(v.decode("utf-8")),
            auto_offset_reset="latest"
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
