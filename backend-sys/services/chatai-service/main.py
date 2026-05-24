import grpc
import asyncio
import logging
import sys
from shared.proto import service_pb2_grpc, service_pb2
from shared.database.engine import SessionLocal
from shared.config import CHATAI_SERVICE_ADDR

logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)

class ChatService(service_pb2_grpc.ChatServiceServicer):
    async def GetAIResponse(self, request, context):
        # 1. Process AI Logic (e.g., call LLM)
        # 2. Save to shared DB using SessionLocal
        return service_pb2.ChatResponse(response="Hello! I am your AI.")

async def serve():
    # Initialize MongoDB unique index on startup
    from shared.database.mongodb import init_mongodb_db, MongoDBManager
    await init_mongodb_db()

    # Start Kafka consumer Chat Worker in background
    from services.workers.kafka_worker import KafkaChatWorker
    chat_worker = KafkaChatWorker()
    chat_worker_task = asyncio.create_task(chat_worker.start())

    server = grpc.aio.server()
    service_pb2_grpc.add_ChatServiceServicer_to_server(ChatService(), server)
    port = CHATAI_SERVICE_ADDR.split(":")[-1]
    server.add_insecure_port(f'[::]:{port}')
    print("ChatAI Service starting on port 50052...")
    await server.start()
    
    try:
        await server.wait_for_termination()
    finally:
        # Gracefully shutdown consumer and close MongoDB client
        await chat_worker.shutdown()
        await chat_worker_task
        await MongoDBManager.close()

if __name__ == "__main__":
    asyncio.run(serve())
