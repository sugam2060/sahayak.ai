from fastapi import FastAPI, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
import grpc
import uvicorn
from contextlib import asynccontextmanager
from shared.proto import service_pb2, service_pb2_grpc
from shared.config import AUTH_SERVICE_ADDR, CHATAI_SERVICE_ADDR, GATEWAY_PORT
from services.api_gateway.middlewares.rate_limiter import SlidingWindowRateLimiter
from services.api_gateway.routers.auth_routers import registration, verification, login, me, refresh, logout

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Setup gRPC Channels
    auth_channel = grpc.aio.insecure_channel(AUTH_SERVICE_ADDR)
    chat_channel = grpc.aio.insecure_channel(CHATAI_SERVICE_ADDR)
    
    # Expose stubs to the app state
    app.state.auth_stub = service_pb2_grpc.AuthServiceStub(auth_channel)
    
    yield
    
    # Shutdown: Close gRPC Channels
    await auth_channel.close()

app = FastAPI(lifespan=lifespan)

# Add CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000","*"],
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

@app.get("/health")
async def health_check():
    return {"status": "ok"}

if __name__ == "__main__":
    uvicorn.run(app, host="localhost", port=GATEWAY_PORT)
