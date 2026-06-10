import asyncio
import logging
import sys
from shared.database.mongodb import init_mongodb_db, MongoDBManager

# Ensure stdout/stderr are line-buffered to avoid console output buffering when run in background
sys.stdout.reconfigure(line_buffering=True)
sys.stderr.reconfigure(line_buffering=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
    force=True
)

# Explicitly ensure chatai_service loggers are set to INFO level
logging.getLogger("chatai_service").setLevel(logging.INFO)


async def serve():
    # Initialize MongoDB unique index on startup
    await init_mongodb_db()

    # Start Kafka consumer Chat Worker in background from chatai-service
    import importlib
    chat_worker_module = importlib.import_module("services.chatai-service.chat_worker")
    chat_worker = chat_worker_module.KafkaChatWorker()
    chat_worker_task = asyncio.create_task(chat_worker.start())

    # Start Kafka consumer Internal Chat Worker in background
    internal_chat_worker_module = importlib.import_module("services.chatai-service.internal_chat.worker")
    KafkaInternalChatWorker = internal_chat_worker_module.KafkaInternalChatWorker
    internal_chat_worker = KafkaInternalChatWorker()
    internal_chat_worker_task = asyncio.create_task(internal_chat_worker.start())

    print("ChatAI Service (Kafka-based) successfully started.")
    
    try:
        # Run a loop to keep the main task alive while the workers are running
        while chat_worker.should_run and internal_chat_worker.should_run:
            await asyncio.sleep(1)
    except (KeyboardInterrupt, asyncio.CancelledError):
        pass
    finally:
        # Gracefully shutdown consumers and close MongoDB client
        print("Stopping ChatAI Service...")
        await chat_worker.shutdown()
        await internal_chat_worker.shutdown()
        await asyncio.gather(chat_worker_task, internal_chat_worker_task, return_exceptions=True)
        await MongoDBManager.close()


if __name__ == "__main__":
    asyncio.run(serve())

