from fastapi import APIRouter, Request, HTTPException, status, Response, Cookie
from typing import Optional
from shared.proto import service_pb2

router = APIRouter(prefix="/auth", tags=["Authentication"])

from fastapi.responses import JSONResponse
from shared.config import COOKIE_DOMAIN

@router.api_route("/refresh_token", methods=["GET", "POST"])
async def refresh_token(
    request: Request, 
    refresh_token: Optional[str] = Cookie(None)
):
    """
    Endpoint to refresh the access token using the refresh_token cookie.
    If valid, sets a new access_token cookie.
    """
    if not refresh_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token missing. Please log in again."
        )
    
    auth_stub = request.app.state.auth_stub
    
    # Extract metadata
    ip_address = request.client.host if request.client else "unknown"
    user_agent = request.headers.get("user-agent", "unknown")

    try:
        # Call gRPC AuthService.RefreshToken
        grpc_request = service_pb2.RefreshTokenRequest(
            refresh_token=refresh_token,
            ip_address=ip_address,
            user_agent=user_agent
        )
        grpc_response = await auth_stub.RefreshToken(grpc_request)
        
        if not grpc_response.success:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=grpc_response.message or "Invalid refresh token."
            )
            
        # 2. To return the full user object (same as /auth/me), 
        # we call VerifyAccessToken with the NEW token.
        verify_request = service_pb2.VerifyAccessTokenRequest(access_token=grpc_response.access_token)
        verify_response = await auth_stub.VerifyAccessToken(verify_request)
        
        if not verify_response.valid:
            # This shouldn't happen if refresh succeeded, but safety first
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Token refreshed but profile could not be retrieved."
            )

        content = {
            "success": True,
            "user": {
                "user_id": verify_response.user_id,
                "organization_id": verify_response.organization_id,
                "organization_name": verify_response.organization_name,
                "role": verify_response.role
            }
        }
        
        response = JSONResponse(content=content)
        
        # Set new access_token in cookie
        response.set_cookie(
            key="access_token",
            value=grpc_response.access_token,
            httponly=True,
            secure=True,  # Set to True in production (HTTPS)
            samesite="lax",
            domain=COOKIE_DOMAIN,
            max_age=3600,   # 1 hour
            path="/"
        )
        
        # Update refresh_token cookie (Rotation)
        response.set_cookie(
            key="refresh_token",
            value=grpc_response.refresh_token,
            httponly=True,
            secure=True,  # Set to True in production (HTTPS)
            samesite="lax",
            domain=COOKIE_DOMAIN,
            max_age=30 * 24 * 3600,  # 30 days
            path="/"
        )

        return response
        
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        
        # Log error for internal tracking
        print(f"Error in /auth/refresh: {str(e)}")
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while refreshing your session."
        )
