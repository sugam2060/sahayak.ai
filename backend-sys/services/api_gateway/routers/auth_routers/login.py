from fastapi import APIRouter, Request, HTTPException, status, Response
from pydantic import BaseModel, EmailStr
from shared.proto import service_pb2

router = APIRouter(prefix="/auth", tags=["Authentication"])

class LoginSchema(BaseModel):
    email: EmailStr
    password: str

from fastapi.responses import JSONResponse

@router.post("/login")
async def login(request: Request, data: LoginSchema):
    auth_stub = request.app.state.auth_stub
    
    try:
        # Extract metadata
        ip_address = request.client.host if request.client else "unknown"
        user_agent = request.headers.get("user-agent", "unknown")

        # Call gRPC AuthService.Login
        grpc_request = service_pb2.LoginRequest(
            email=data.email,
            password=data.password,
            ip_address=ip_address,
            user_agent=user_agent
        )
        
        grpc_response = await auth_stub.Login(grpc_request)
        
        if not grpc_response.success:
            # Check if it was a verification error
            if "verify your email" in grpc_response.message.lower() or "not verified" in grpc_response.message.lower():
                return {
                    "success": False,
                    "message": grpc_response.message,
                    "is_verified": False
                }
            
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=grpc_response.message
            )
            
        # Create response object
        content = {
            "success": True,
            "message": grpc_response.message,
            "user_id": grpc_response.user_id,
            "organization_id": grpc_response.organization_id,
            "is_verified": grpc_response.is_verified,
            "full_name": grpc_response.full_name,
            "organization_name": grpc_response.organization_name,
            "organization_slug": grpc_response.organization_slug,
            "email": grpc_response.email
        }
        
        response = JSONResponse(content=content)
        
        # Store tokens in HttpOnly cookies
        response.set_cookie(
            key="access_token",
            value=grpc_response.access_token,
            httponly=True,
            secure=True,  # Set to True in production (HTTPS)
            samesite="none",
            max_age=3600,   # 1 hour
            path="/"
        )
        response.set_cookie(
            key="refresh_token",
            value=grpc_response.refresh_token,
            httponly=True,
            secure=True,  # Set to True in production (HTTPS)
            samesite="none",
            max_age=30 * 24 * 3600,  # 30 days
            path="/"
        )

        return response
        
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        
        # Check for gRPC errors specifically to avoid leaking internal details
        import grpc
        if isinstance(e, grpc.RpcError):
            status_code = e.code()
            if status_code == grpc.StatusCode.UNAVAILABLE:
                raise HTTPException(status_code=503, detail="Authentication service is temporarily unavailable.")
            if status_code == grpc.StatusCode.ALREADY_EXISTS:
                raise HTTPException(status_code=409, detail=e.details())
            
            # For general internal errors, don't leak the gRPC detail string
            raise HTTPException(
                status_code=500, 
                detail="An internal error occurred in the authentication service. Please try again later."
            )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred."
        )
