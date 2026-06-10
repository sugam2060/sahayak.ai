import asyncio
import json
import logging
from typing import Optional
from aiokafka import AIOKafkaConsumer
from shared.config import KAFKA_BOOTSTRAP_SERVERS, KAFKA_SECURITY_PROTOCOL
from .manager import manager

logger = logging.getLogger("api_gateway.internal_chat.consumer")

class InternalChatWSConsumer:
    def __init__(self):
        self.task: Optional[asyncio.Task] = None

    async def start(self):
        if self.task is None or self.task.done():
            self.task = asyncio.create_task(self.consume_events())
            logger.info("[Internal WS Gateway] Started background Kafka internal_chat_websocket consumer task.")

    async def stop(self):
        if self.task and not self.task.done():
            logger.info("[Internal WS Gateway] Stopping background Kafka internal_chat_websocket consumer task...")
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
            self.task = None

    async def consume_events(self):
        try:
            bootstrap_servers = [s.strip() for s in KAFKA_BOOTSTRAP_SERVERS.split(",")]
            logger.info(f"[Internal WS Consumer] Starting on brokers: {bootstrap_servers}")
            
            kwargs = {
                "bootstrap_servers": bootstrap_servers,
                "group_id": "api-gateway-internal-ws-group",
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
                "internal_chat_websocket",
                **kwargs
            )
            
            await consumer.start()
            logger.info("[Internal WS Consumer] Successfully connected and listening on 'internal_chat_websocket'.")
            
            try:
                while True:
                    msg_pack = await consumer.getmany(timeout_ms=1000)
                    for tp, messages in msg_pack.items():
                        for msg in messages:
                            event = msg.value
                            org_id = event.get("org_id")
                            chat_type = event.get("type")
                            if not org_id:
                                continue
                                
                            logger.debug(f"[Internal WS Consumer] Received internal event: type={chat_type}, org={org_id}")
                            
                            if chat_type in ("direct", "group"):
                                user_ids = event.get("user_ids", [])
                                await manager.broadcast_to_users(org_id, user_ids, event)
                            elif chat_type == "org":
                                await manager.broadcast_to_org(org_id, event)
            finally:
                await consumer.stop()
                logger.info("[Internal WS Consumer] Stopped.")
        except asyncio.CancelledError:
            logger.info("[Internal WS Consumer] Task cancelled.")
        except Exception as e:
            logger.error(f"[Internal WS Consumer] Exception: {e}", exc_info=True)

# Global instance
ws_consumer = InternalChatWSConsumer()
