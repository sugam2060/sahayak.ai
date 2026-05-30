import asyncio
import logging
import sys
from services.workers.kafka_worker import KafkaMailWorker

# Set up logging configuration only if not already configured
logger = logging.getLogger("kafka_mail_worker")
if not logger.handlers:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)]
    )
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("aiokafka").setLevel(logging.WARNING)

async def main():
    # Initialize MongoDB on startup
    from shared.database.mongodb import init_mongodb_db, MongoDBManager
    await init_mongodb_db()

    # Start gRPC server
    from services.workers.grpc_server import start_grpc_server
    server = await start_grpc_server()

    # Start Mail Worker
    worker = KafkaMailWorker()
    logger.info("Starting Kafka Mail Worker...")
    worker_task = asyncio.create_task(worker.start())

    try:
        # Keep alive
        while worker.should_run:
            await asyncio.sleep(1)
    except (KeyboardInterrupt, asyncio.CancelledError):
        logger.info("Termination requested.")
    finally:
        logger.info("Stopping Workers Service...")
        await server.stop(5)
        await worker.shutdown()
        try:
            await worker_task
        except Exception as e:
            logger.error(f"Error stopping worker task: {e}")
        await MongoDBManager.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Worker terminated by keyboard interrupt.")