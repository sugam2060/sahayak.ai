import json
import logging
from aiokafka import AIOKafkaProducer
from shared.config import KAFKA_BOOTSTRAP_SERVERS

logger = logging.getLogger(__name__)

class KafkaProducerPool:
    _producer = None

    @classmethod
    async def get_producer(cls):
        """
        Lazily gets/initializes the AIOKafkaProducer instance.
        """
        if cls._producer is None:
            bootstrap_servers = [s.strip() for s in KAFKA_BOOTSTRAP_SERVERS.split(",")]
            logger.info(f"Initializing Kafka producer with brokers: {bootstrap_servers}")
            cls._producer = AIOKafkaProducer(
                bootstrap_servers=bootstrap_servers,
                value_serializer=lambda v: json.dumps(v).encode("utf-8")
            )
            await cls._producer.start()
        return cls._producer

    @classmethod
    async def send_message(cls, topic: str, value: dict):
        """
        Asynchronously sends a JSON-serializable message to the specified Kafka topic.
        """
        try:
            producer = await cls.get_producer()
            await producer.send_and_wait(topic, value)
        except Exception as e:
            logger.error(f"Failed to publish message to Kafka topic {topic}: {str(e)}")
            raise e

    @classmethod
    async def close(cls):
        """
        Gracefully closes the Kafka producer instance.
        """
        if cls._producer:
            logger.info("Stopping Kafka producer...")
            await cls._producer.stop()
            cls._producer = None
