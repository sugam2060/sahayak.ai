import asyncio
import logging
import sys
from shared.database.mongodb import init_mongodb_db, MongoDBManager

logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)

async def serve():
    # Initialize MongoDB unique index on startup
    await init_mongodb_db()

    # Start Kafka consumer Chat Worker in background from chatai-service
    import importlib
    chat_worker_module = importlib.import_module("services.chatai-service.chat_worker")
    chat_worker = chat_worker_module.KafkaChatWorker()
    chat_worker_task = asyncio.create_task(chat_worker.start())

    print("ChatAI Service (Kafka-based) successfully started.")
    
    try:
        # Run a loop to keep the main task alive while the worker is running
        while chat_worker.should_run:
            await asyncio.sleep(1)
    except (KeyboardInterrupt, asyncio.CancelledError):
        pass
    finally:
        # Gracefully shutdown consumer and close MongoDB client
        await chat_worker.shutdown()
        await chat_worker_task
        await MongoDBManager.close()

if __name__ == "__main__":
    asyncio.run(serve())
