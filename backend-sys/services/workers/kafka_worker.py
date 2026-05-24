import asyncio
import json
import logging
import signal
import sys
from aiokafka import AIOKafkaConsumer
from shared.config import KAFKA_BOOTSTRAP_SERVERS
from services.workers.mail_service import send_verification_email
import httpx
from datetime import datetime, timezone
from shared.database.mongodb import MongoDBManager
from shared.database.schema.chat_message_mongo import MessageDetail, ConversationUser, ConversationMongo

# Set up logging
logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("aiokafka").setLevel(logging.WARNING)
logger = logging.getLogger("kafka_mail_worker")

class KafkaMailWorker:
    def __init__(self):
        self.consumer = None
        self.should_run = True

    async def start(self):
        bootstrap_servers = [s.strip() for s in KAFKA_BOOTSTRAP_SERVERS.split(",")]
        logger.info(f"Connecting mail worker to Kafka brokers: {bootstrap_servers}")
        
        self.consumer = AIOKafkaConsumer(
            "mail-events",
            bootstrap_servers=bootstrap_servers,
            group_id="mail-worker-group",
            value_deserializer=lambda v: json.loads(v.decode("utf-8")),
            auto_offset_reset="earliest"
        )
        
        await self.consumer.start()
        logger.info("Kafka Mail Worker Consumer successfully started and listening on 'mail-events' topic.")
        
        # Setup signal handlers for graceful shutdown
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                loop.add_signal_handler(sig, lambda: asyncio.create_task(self.shutdown()))
            except NotImplementedError:
                # signal handlers are not fully supported on some Windows setups or in non-main threads, fallback is acceptable
                pass

        try:
            while self.should_run:
                # We fetch messages with a timeout to allow checking self.should_run periodically
                msg_pack = await self.consumer.getmany(timeout_ms=1000)
                for topic_partition, messages in msg_pack.items():
                    for msg in messages:
                        payload = msg.value
                        email = payload.get("email")
                        subject = payload.get("subject")
                        html_content = payload.get("html_content")
                        
                        logger.info(f"Processing verification mail event for: {email}")
                        if not email or not subject or not html_content:
                            logger.warning(f"Skipping invalid mail event payload: {payload}")
                            continue
                        
                        try:
                            # Run the blocking SMTP function inside thread pool executor
                            success = await loop.run_in_executor(
                                None,
                                send_verification_email,
                                email,
                                subject,
                                html_content
                            )
                            if success:
                                logger.info(f"Verification email successfully sent to {email}")
                            else:
                                logger.error(f"Verification email sending failed (returned False) for {email}")
                        except Exception as e:
                            logger.error(f"Failed to send email to {email}: {str(e)}")
        except asyncio.CancelledError:
            pass
        finally:
            await self.cleanup()

    async def shutdown(self):
        logger.info("Shutdown signal received. Stopping worker...")
        self.should_run = False

    async def cleanup(self):
        if self.consumer:
            logger.info("Closing Kafka consumer connection...")
            await self.consumer.stop()
            self.consumer = None
            logger.info("Kafka consumer connection closed.")


class KafkaChatWorker:
    def __init__(self):
        self.consumer = None
        self.should_run = True

    async def start(self):
        bootstrap_servers = [s.strip() for s in KAFKA_BOOTSTRAP_SERVERS.split(",")]
        logger.info(f"Connecting chat worker to Kafka brokers: {bootstrap_servers}")
        
        self.consumer = AIOKafkaConsumer(
            "chat_service",
            bootstrap_servers=bootstrap_servers,
            group_id="chat-worker-group",
            value_deserializer=lambda v: json.loads(v.decode("utf-8")),
            auto_offset_reset="earliest"
        )
        
        await self.consumer.start()
        logger.info("Kafka Chat Worker Consumer successfully started and listening on 'chat_service' topic.")
        
        # Setup signal handlers for graceful shutdown
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                loop.add_signal_handler(sig, lambda: asyncio.create_task(self.shutdown()))
            except NotImplementedError:
                # signal handlers are not fully supported on some Windows setups or in non-main threads, fallback is acceptable
                pass

        try:
            db = MongoDBManager.get_db()
            while self.should_run:
                # We fetch messages with a timeout to allow checking self.should_run periodically
                msg_pack = await self.consumer.getmany(timeout_ms=1000)
                for topic_partition, messages in msg_pack.items():
                    for msg in messages:
                        event = msg.value
                        org_id = event.get("org_id")
                        bot_name = event.get("bot_name")
                        bot_token = event.get("bot_token")
                        platform = event.get("platform", "telegram")
                        direction = event.get("direction", "inbound")
                        
                        logger.debug(f"Processing {direction} chat event for org: {org_id}")
                        if not org_id or not bot_token:
                            logger.warning(f"Skipping invalid chat event payload: {event}")
                            continue
                        
                        try:
                            if direction == "inbound":
                                payload = event.get("payload", {})
                                # 1. Parse Telegram details
                                message = payload.get("message", {})
                                if not message:
                                    logger.info("Telegram payload has no message block. Skipping.")
                                    continue
                                    
                                chat = message.get("chat", {})
                                sender = message.get("from", {})
                                text = message.get("text", "")
                                
                                chat_id = chat.get("id")
                                sender_id = sender.get("id")
                                if not chat_id or not sender_id:
                                    logger.warning(f"No chat_id or sender_id found in message: {message}")
                                    continue
                                    
                                sender_name = sender.get("first_name", "")
                                if sender.get("last_name"):
                                    sender_name += " " + sender.get("last_name")
                                sender_name = sender_name.strip() or "Unknown"
                                sender_username = sender.get("username")
                                
                                # Find existing conversation to get current messages length
                                conv = await db.conversations.find_one({
                                    "platform": platform,
                                    "user.sender_id": sender_id
                                })
                                
                                next_message_id = 1
                                if conv and "messages" in conv:
                                    next_message_id = len(conv["messages"]) + 1
                                    
                                # Create validated Inbound MessageDetail
                                inbound_msg = MessageDetail(
                                    message_id=next_message_id,
                                    direction="inbound",
                                    sender_id=sender_id,
                                    sender_name=sender_name,
                                    text=text,
                                    created_at=datetime.now(timezone.utc)
                                )
                                
                                # 2. Get/Create the Conversation document (unique per sender_id and platform)
                                user_data = {
                                    "sender_id": sender_id,
                                    "sender_name": sender_name,
                                    "sender_username": sender_username
                                }
                                
                                now = datetime.now(timezone.utc)
                                await db.conversations.update_one(
                                    {
                                        "platform": platform,
                                        "user.sender_id": sender_id
                                    },
                                    {
                                        "$setOnInsert": {
                                            "organization_id": org_id,
                                            "bot_name": bot_name,
                                            "chat_id": chat_id,
                                            "user": user_data,
                                            "created_at": now
                                        },
                                        "$set": {
                                            "updated_at": now
                                        },
                                        "$push": {
                                            "messages": inbound_msg.model_dump()
                                        }
                                    },
                                    upsert=True
                                )
                                logger.debug(f"Saved inbound message {next_message_id} from {sender_name} to MongoDB.")
                                
                                # Publish inbound message to Kafka chat_websocket topic
                                try:
                                    from shared.kafka_producer import KafkaProducerPool
                                    ws_event = {
                                        "org_id": str(org_id),
                                        "platform": platform,
                                        "sender_id": sender_id,
                                        "type": "new_message",
                                        "message": inbound_msg.model_dump(mode="json")
                                    }
                                    await KafkaProducerPool.send_message("chat_websocket", ws_event)
                                    logger.debug(f"Published inbound message event to chat_websocket for org: {org_id}")
                                except Exception as e:
                                    logger.error(f"Failed to publish inbound message to chat_websocket: {e}")
                                
                            elif direction == "outbound":
                                chat_id = event.get("chat_id")
                                sender_id = event.get("sender_id")
                                text = event.get("text", "")
                                
                                if not chat_id or not sender_id:
                                    logger.warning(f"Skipping outbound event missing chat_id or sender_id: {event}")
                                    continue
                                    
                                # Find existing conversation
                                conv = await db.conversations.find_one({
                                    "platform": platform,
                                    "user.sender_id": sender_id
                                })
                                
                                next_message_id = 1
                                if conv and "messages" in conv:
                                    next_message_id = len(conv["messages"]) + 1
                                    
                                # Create validated Outbound MessageDetail
                                outbound_msg = MessageDetail(
                                    message_id=next_message_id,
                                    direction="outbound",
                                    sender_id=0,  # Bot/System sender ID
                                    sender_name=bot_name,
                                    text=text,
                                    created_at=datetime.now(timezone.utc)
                                )
                                
                                await db.conversations.update_one(
                                    {
                                        "platform": platform,
                                        "user.sender_id": sender_id
                                    },
                                    {
                                        "$set": {
                                            "updated_at": datetime.now(timezone.utc)
                                        },
                                        "$push": {
                                            "messages": outbound_msg.model_dump()
                                        }
                                    }
                                )
                                logger.debug(f"Saved outbound reply message {next_message_id} to MongoDB.")

                                # Publish outbound message to Kafka chat_websocket topic
                                try:
                                    from shared.kafka_producer import KafkaProducerPool
                                    ws_event = {
                                        "org_id": str(org_id),
                                        "platform": platform,
                                        "sender_id": sender_id,
                                        "type": "new_message",
                                        "message": outbound_msg.model_dump(mode="json")
                                    }
                                    await KafkaProducerPool.send_message("chat_websocket", ws_event)
                                    logger.debug(f"Published outbound message event to chat_websocket for org: {org_id}")
                                except Exception as e:
                                    logger.error(f"Failed to publish outbound message to chat_websocket: {e}")
                                
                                # Send message back to Telegram user via Bot API
                                async with httpx.AsyncClient() as client:
                                    telegram_url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
                                    tg_payload = {
                                        "chat_id": chat_id,
                                        "text": text
                                    }
                                    logger.debug(f"Sending manual reply to Telegram chat {chat_id} via Bot API...")
                                    tg_response = await client.post(telegram_url, json=tg_payload, timeout=10.0)
                                    if tg_response.status_code == 200:
                                        logger.debug("Successfully sent manual reply to Telegram user.")
                                    else:
                                        logger.error(f"Failed to send manual reply to Telegram: {tg_response.status_code} - {tg_response.text}")
                                        
                        except Exception as e:
                            logger.error(f"Error processing chat event: {str(e)}", exc_info=True)
        except asyncio.CancelledError:
            pass
        finally:
            await self.cleanup()

    async def shutdown(self):
        logger.info("Shutdown signal received. Stopping worker...")
        self.should_run = False

    async def cleanup(self):
        if self.consumer:
            logger.info("Closing Kafka consumer connection...")
            await self.consumer.stop()
            self.consumer = None
            logger.info("Kafka consumer connection closed.")

if __name__ == "__main__":
    worker = KafkaMailWorker()
    try:
        asyncio.run(worker.start())
    except KeyboardInterrupt:
        logger.info("Worker terminated by keyboard interrupt.")
