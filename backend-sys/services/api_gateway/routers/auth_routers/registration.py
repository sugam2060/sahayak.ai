from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel, EmailStr
from shared.proto import service_pb2, service_pb2_grpc
import grpc

router = APIRouter(prefix="/auth", tags=["Authentication"])

class RegistrationRequest(BaseModel):
    org_name: str
    org_slug: str
    full_name: str
    email: EmailStr
    password: str

@router.post("/register")
async def register(request: Request, reg_request: RegistrationRequest):
    try:
        # Use the stub from app.state (managed by lifespan)
        stub = request.app.state.auth_stub
        
        response = await stub.Register(
            service_pb2.RegisterRequest(
                org_name=reg_request.org_name,
                org_slug=reg_request.org_slug,
                user_full_name=reg_request.full_name,
                user_email=reg_request.email,
                user_password=reg_request.password
            )
        )
        return {
            "organization_id": response.organization_id,
            "user_id": response.user_id,
            "message": response.message
        }
    except grpc.aio.AioRpcError as e:
        # Map gRPC status codes to HTTP status codes
        status_code = 500
        detail = "An internal server error occurred."
        
        if e.code() == grpc.StatusCode.ALREADY_EXISTS:
            status_code = 409
            detail = e.details()
        elif e.code() == grpc.StatusCode.INVALID_ARGUMENT:
            status_code = 400
            detail = e.details()
        elif e.code() == grpc.StatusCode.UNAUTHENTICATED:
            status_code = 401
            detail = e.details()
        elif e.code() == grpc.StatusCode.PERMISSION_DENIED:
            status_code = 403
            detail = e.details()
        elif e.code() == grpc.StatusCode.UNAVAILABLE:
            status_code = 503
            detail = "Authentication service is temporarily unavailable."
        
        raise HTTPException(status_code=status_code, detail=detail)
