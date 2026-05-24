import asyncio
import json
import logging
import signal
import sys
from aiokafka import AIOKafkaConsumer
from shared.config import KAFKA_BOOTSTRAP_SERVERS
from .chat_service import handle_chat_event

logger = logging.getLogger("chatai_service.chat_worker")

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
                            # Delegate processing logic directly to chat_service
                            await handle_chat_event(event)
                        except Exception as e:
                            logger.error(f"Error processing chat event via chat service: {str(e)}", exc_info=True)
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
