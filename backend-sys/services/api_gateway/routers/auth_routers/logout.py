from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from shared.proto import service_pb2

router = APIRouter(prefix="/auth", tags=["Authentication"])

@router.post("/logout")
async def logout(request: Request):
    auth_stub = request.app.state.auth_stub
    
    # 1. Get Access Token from cookies
    access_token = request.cookies.get("access_token")
    
    if access_token:
        try:
            # 2. Call gRPC AuthService.Logout to invalidate sessions on backend
            grpc_request = service_pb2.LogoutRequest(access_token=access_token)
            await auth_stub.Logout(grpc_request)
        except Exception as e:
            # We log the error but still proceed to clear cookies to ensure client-side logout
            print(f"Error calling gRPC Logout: {str(e)}")
            pass

    # 3. Create response and clear cookies
    response = JSONResponse(content={
        "success": True,
        "message": "Logged out successfully from all devices."
    })
    
    # Securely remove tokens from the browser
    response.delete_cookie(key="access_token", path="/")
    response.delete_cookie(key="refresh_token", path="/")
    
    return response
