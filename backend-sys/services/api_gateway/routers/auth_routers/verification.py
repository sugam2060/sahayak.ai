from fastapi import APIRouter, HTTPException, Request
from shared.proto import service_pb2
import grpc

router = APIRouter(prefix="/auth", tags=["Authentication"])

@router.get("/verify/{token}")
async def verify_email(request: Request, token: str):
    """
    Endpoint to verify a user's email using a token.
    Proxies the request to the Auth Service via gRPC.
    """
    try:
        # Use the stub from app.state (managed by lifespan)
        stub = request.app.state.auth_stub
        
        response = await stub.VerifyEmail(
            service_pb2.VerifyEmailRequest(token=token)
        )
        
        if not response.success:
            raise HTTPException(status_code=400, detail=response.message)
            
        return {
            "success": True,
            "message": response.message
        }
        
    except grpc.aio.AioRpcError as e:
        status_code = 500
        detail = "An internal server error occurred in the authentication service."
        if e.code() == grpc.StatusCode.UNAVAILABLE:
            status_code = 503
            detail = "Authentication service is temporarily unavailable."
        raise HTTPException(status_code=status_code, detail=detail)
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail="An unexpected error occurred.")
