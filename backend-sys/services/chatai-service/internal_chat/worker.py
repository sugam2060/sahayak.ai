import asyncio
import json
import logging
import signal
from datetime import datetime, timezone
from uuid import uuid4
from aiokafka import AIOKafkaConsumer
from shared.config import KAFKA_BOOTSTRAP_SERVERS, KAFKA_SECURITY_PROTOCOL
from shared.kafka_producer import KafkaProducerPool
from shared.database.schema.internal_chat_mongo import InternalMessageDetail, CustomerChatRequestDetail, HandoffRequestDetail
from .service import InternalChatService

logger = logging.getLogger("chatai_service.internal_chat.worker")

class KafkaInternalChatWorker:
    def __init__(self):
        self.consumer = None
        self.should_run = True
        self.service = InternalChatService()

    async def start(self):
        bootstrap_servers = [s.strip() for s in KAFKA_BOOTSTRAP_SERVERS.split(",")]
        logger.info(f"Connecting internal chat worker to Kafka brokers: {bootstrap_servers}")
        
        kwargs = {
            "bootstrap_servers": bootstrap_servers,
            "group_id": "internal-chat-worker-group",
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
            
        # Subscribe to direct, group, and org-wide internal chat topics
        self.consumer = AIOKafkaConsumer(
            "internal_chat.direct",
            "internal_chat.group",
            "internal_chat.org",
            **kwargs
        )
        
        await self.consumer.start()
        logger.info("Kafka Internal Chat Worker successfully started and listening on internal_chat.* topics.")
        
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                loop.add_signal_handler(sig, lambda: asyncio.create_task(self.shutdown()))
            except NotImplementedError:
                pass

        try:
            while self.should_run:
                msg_pack = await self.consumer.getmany(timeout_ms=1000)
                for topic_partition, messages in msg_pack.items():
                    for msg in messages:
                        event = msg.value
                        topic = topic_partition.topic
                        logger.debug(f"Processing event from topic {topic}: {event}")
                        try:
                            await self.process_chat_event(topic, event)
                        except Exception as e:
                            logger.error(f"Error processing internal chat event on topic {topic}: {e}", exc_info=True)
        except asyncio.CancelledError:
            pass
        finally:
            await self.cleanup()

    async def process_chat_event(self, topic: str, event: dict):
        org_id = event.get("org_id")
        sender_id = event.get("sender_id")
        sender_name = event.get("sender_name")
        text = event.get("text", "")
        msg_type = event.get("message_type", "text")
        
        if not org_id or not sender_id or not sender_name:
            logger.warning(f"Skipping invalid internal chat event (missing org/sender info): {event}")
            return

        # Build Customer Chat Request Detail if type matches
        req_detail = None
        if msg_type == "customer_chat_request":
            req_data = event.get("customer_chat_request", {})
            req_detail = CustomerChatRequestDetail(
                platform=req_data.get("platform"),
                sender_id=str(req_data.get("sender_id")),
                status="pending"
            )

        # Build Handoff Request Detail if type matches
        handoff_detail = None
        if msg_type == "handoff_request":
            hr_data = event.get("handoff_request", {})
            handoff_detail = HandoffRequestDetail(
                id=hr_data.get("id", str(uuid4())),
                conversation_id=hr_data.get("conversation_id", ""),
                requester_id=hr_data.get("requester_id", ""),
                handler_id=hr_data.get("handler_id", ""),
                org_id=hr_data.get("org_id", org_id),
                status=hr_data.get("status", "pending"),
                timestamp=hr_data.get("timestamp", int(datetime.now(timezone.utc).timestamp() * 1000))
            )

        message_detail = InternalMessageDetail(
            sender_id=str(sender_id),
            sender_name=sender_name,
            text=text,
            message_type=msg_type,
            customer_chat_request=req_detail,
            handoff_request=handoff_detail
        )

        if topic == "internal_chat.direct":
            recipient_id = event.get("recipient_id")
            if not recipient_id:
                logger.warning(f"Skipping direct message with no recipient: {event}")
                return
                
            # Retrieve or create DM conversation room
            convo = await self.service.get_or_create_direct_conversation(org_id, sender_id, recipient_id)
            await self.service.add_message_to_conversation(convo["_id"], message_detail)
            
            # Publish to WebSocket fan-out topic
            ws_payload = {
                "org_id": org_id,
                "type": "direct",
                "convo_id": convo["_id"],
                "user_ids": [str(sender_id), str(recipient_id)],
                "event_type": "new_message",
                "message": message_detail.model_dump(mode="json")
            }
            await KafkaProducerPool.send_message("internal_chat_websocket", ws_payload)

        elif topic == "internal_chat.group":
            group_id = event.get("group_id")
            if not group_id:
                logger.warning(f"Skipping group message with no group_id: {event}")
                return
                
            convo = await self.service.get_group_conversation(group_id)
            if not convo:
                logger.warning(f"Skipping group message: group conversation '{group_id}' not found.")
                return
                
            # Security verification
            if str(sender_id) not in [str(u) for u in convo["user_ids"]]:
                logger.warning(f"User '{sender_id}' tried to message group '{group_id}' but is not a member.")
                return
                
            await self.service.add_message_to_conversation(group_id, message_detail)
            
            ws_payload = {
                "org_id": org_id,
                "type": "group",
                "convo_id": group_id,
                "user_ids": [str(u) for u in convo["user_ids"]],
                "event_type": "new_message",
                "message": message_detail.model_dump(mode="json")
            }
            await KafkaProducerPool.send_message("internal_chat_websocket", ws_payload)

        elif topic == "internal_chat.org":
            convo = await self.service.get_or_create_org_conversation(org_id)
            await self.service.add_message_to_conversation(convo["_id"], message_detail)
            
            ws_payload = {
                "org_id": org_id,
                "type": "org",
                "convo_id": convo["_id"],
                "event_type": "new_message",
                "message": message_detail.model_dump(mode="json")
            }
            await KafkaProducerPool.send_message("internal_chat_websocket", ws_payload)

    async def shutdown(self):
        logger.info("Internal chat worker shutdown signal received. Stopping worker...")
        self.should_run = False

    async def cleanup(self):
        if self.consumer:
            logger.info("Closing Kafka internal consumer connection...")
            await self.consumer.stop()
            self.consumer = None
            logger.info("Kafka internal consumer connection closed.")
