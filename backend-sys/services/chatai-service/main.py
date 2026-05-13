import grpc
import asyncio
from shared.proto import service_pb2_grpc, service_pb2
from shared.database.engine import SessionLocal
from shared.config import CHATAI_SERVICE_ADDR

class ChatService(service_pb2_grpc.ChatServiceServicer):
    async def GetAIResponse(self, request, context):
        # 1. Process AI Logic (e.g., call LLM)
        # 2. Save to shared DB using SessionLocal
        return service_pb2.ChatResponse(response="Hello! I am your AI.")

async def serve():
    server = grpc.aio.server()
    service_pb2_grpc.add_ChatServiceServicer_to_server(ChatService(), server)
    port = CHATAI_SERVICE_ADDR.split(":")[-1]
    server.add_insecure_port(f'[::]:{port}')
    print("ChatAI Service starting on port 50052...")
    await server.start()
    await server.wait_for_termination()

if __name__ == "__main__":
    asyncio.run(serve())
