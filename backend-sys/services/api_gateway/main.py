from fastapi import FastAPI, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
import grpc
import uvicorn
import logging
import sys

# Configure standard logging — INFO for our app, WARNING for noisy libraries
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
# Suppress noisy third-party loggers
logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
logging.getLogger("aiokafka").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)
from contextlib import asynccontextmanager
from shared.proto import service_pb2, service_pb2_grpc
from shared.config import AUTH_SERVICE_ADDR, WORKERS_SERVICE_ADDR, GATEWAY_PORT, APP_ENV
from services.api_gateway.middlewares.rate_limiter import SlidingWindowRateLimiter
from services.api_gateway.routers.auth_routers import registration, verification, login, me, refresh, logout
from services.api_gateway.routers.connectors import connector_route
from services.api_gateway.routers.chat_routers import telegram_webhook_router, chats_router, instagram_webhook_router
from services.api_gateway.routers import products, orders
from services.api_gateway.routers.ai_config import router as ai_config_router
from services.api_gateway.routers.ticket import router as ticket_router
from services.api_gateway.routers.teams import router as teams_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Setup gRPC Channels
    auth_channel = grpc.aio.insecure_channel(AUTH_SERVICE_ADDR)
    workers_channel = grpc.aio.insecure_channel(WORKERS_SERVICE_ADDR)
    
    # Expose stubs to the app state
    app.state.auth_stub = service_pb2_grpc.AuthServiceStub(auth_channel)
    app.state.product_stub = service_pb2_grpc.ProductServiceStub(workers_channel)
    app.state.order_stub = service_pb2_grpc.OrderServiceStub(workers_channel)
    app.state.ticket_stub = service_pb2_grpc.TicketServiceStub(workers_channel)
    
    from shared.database.mongodb import MongoDBManager
    
    # Start WebSocket consumer task
    from services.api_gateway.routers.chat_routers.chats import start_ws_kafka_consumer, stop_ws_kafka_consumer
    try:
        await start_ws_kafka_consumer()
    except Exception as e:
        print(f"Failed to start WebSocket Kafka consumer on Gateway startup: {e}")
    
    yield
    
    # Shutdown: Close gRPC Channels and MongoDB client
    await stop_ws_kafka_consumer()
    await auth_channel.close()
    await workers_channel.close()
    await MongoDBManager.close()

# Disable API documentation endpoints in production
if APP_ENV == "production":
    app = FastAPI(
        lifespan=lifespan,
        docs_url=None,
        redoc_url=None,
        openapi_url=None
    )
else:
    app = FastAPI(lifespan=lifespan)

# Add CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000","https://sahayak.sugampudasain.xyz"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add Rate Limiting Middleware (Sliding Window Counter)
# Targeted only at authentication and chat endpoints
app.add_middleware(
    SlidingWindowRateLimiter, 
    window_size=60, 
    max_requests=10,
    include_paths=["/auth", "/chat", "/health"],
    exclude_paths=["/auth/me"]
)

# Include Routers
app.include_router(registration.router)
app.include_router(verification.router)
app.include_router(login.router)
app.include_router(me.router)
app.include_router(refresh.router)
app.include_router(logout.router)
app.include_router(connector_route.router)
app.include_router(telegram_webhook_router)
app.include_router(instagram_webhook_router)
app.include_router(chats_router)
app.include_router(products.router)
app.include_router(orders.router)
app.include_router(ai_config_router)
app.include_router(ticket_router)
app.include_router(teams_router)

@app.get("/health")
async def health_check():
    return {"status": "ok"}

if __name__ == "__main__":
    uvicorn.run(app, host="localhost", port=GATEWAY_PORT, log_level="info")
