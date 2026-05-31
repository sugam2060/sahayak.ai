import json
import logging
from aiokafka import AIOKafkaProducer
from shared.config import KAFKA_BOOTSTRAP_SERVERS, KAFKA_SECURITY_PROTOCOL, AWS_REGION

logger = logging.getLogger(__name__)

def msk_oauth_callback(oauth_bearer_config):
    """
    SASL OAuth Token Provider callback using aws-msk-iam-sasl-signer.
    """
    from aws_msk_iam_sasl_signer import MSKAuthTokenProvider
    token, _ = MSKAuthTokenProvider.generate_auth_token(AWS_REGION)
    return token

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
            
            kwargs = {
                "bootstrap_servers": bootstrap_servers,
                "value_serializer": lambda v: json.dumps(v).encode("utf-8")
            }
            
            if KAFKA_SECURITY_PROTOCOL == "SASL_SSL":
                logger.info("Using SASL_SSL OAUTHBEARER with MSK IAM Signer for Kafka connection")
                kwargs.update({
                    "security_protocol": "SASL_SSL",
                    "sasl_mechanism": "OAUTHBEARER",
                    "sasl_oauth_token_provider": msk_oauth_callback
                })
                
            cls._producer = AIOKafkaProducer(**kwargs)
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
