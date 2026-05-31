import asyncio
import json
import logging
import signal
import sys
from aiokafka import AIOKafkaConsumer
from shared.config import KAFKA_BOOTSTRAP_SERVERS
from services.workers.mail_service import send_verification_email

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
        
        from shared.config import KAFKA_SECURITY_PROTOCOL
        kwargs = {
            "bootstrap_servers": bootstrap_servers,
            "group_id": "mail-worker-group",
            "value_deserializer": lambda v: json.loads(v.decode("utf-8")),
            "auto_offset_reset": "earliest"
        }
        
        if KAFKA_SECURITY_PROTOCOL == "SASL_SSL":
            from shared.kafka_producer import msk_oauth_callback
            kwargs.update({
                "security_protocol": "SASL_SSL",
                "sasl_mechanism": "OAUTHBEARER",
                "sasl_oauth_token_provider": msk_oauth_callback
            })
            
        self.consumer = AIOKafkaConsumer(
            "mail-events",
            **kwargs
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


