from fastapi import APIRouter, Request, HTTPException, status, Depends, Cookie
from typing import Optional
from shared.proto import service_pb2

router = APIRouter(prefix="/auth", tags=["Authentication"])

async def get_current_user(
    request: Request,
    access_token: Optional[str] = Cookie(None)
):
    """
    FastAPI Dependency to verify the access token from cookies.
    It calls the AuthService.VerifyAccessToken gRPC method.
    """
    if not access_token:
        # Check if we have a refresh token to attempt a redirect/refresh
        if request.cookies.get("refresh_token"):
            raise HTTPException(
                status_code=status.HTTP_307_TEMPORARY_REDIRECT,
                headers={"Location": "/auth/refresh_token"}
            )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication token missing. Please log in."
        )
    
    auth_stub = request.app.state.auth_stub
    
    try:
        # Call gRPC AuthService.VerifyAccessToken
        grpc_request = service_pb2.VerifyAccessTokenRequest(access_token=access_token)
        grpc_response = await auth_stub.VerifyAccessToken(grpc_request)
        
        if not grpc_response.valid:
            if request.cookies.get("refresh_token"):
                raise HTTPException(
                    status_code=status.HTTP_307_TEMPORARY_REDIRECT,
                    headers={"Location": "/auth/refresh_token"}
                )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=grpc_response.message or "Invalid or expired session."
            )
            
        return {
            "user_id": grpc_response.user_id,
            "organization_id": grpc_response.organization_id,
            "organization_name": grpc_response.organization_name,
            "role": grpc_response.role
        }
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        
        # Log error for internal tracking
        print(f"Error in get_current_user dependency: {str(e)}")
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while verifying your session."
        )

@router.get("/me")
async def read_users_me(current_user: dict = Depends(get_current_user)):
    """
    Endpoint to retrieve the current logged-in user's details.
    Uses get_current_user as a dependency.
    """
    return {
        "success": True,
        "user": current_user
    }
