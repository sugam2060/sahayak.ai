import jwt
from shared.proto import service_pb2
from shared.config import JWT_SECRET, JWT_ALGORITHM
from services.auth_service.refresh import force_user_logout
from services.auth_service.auth_utils import decode_access_token

async def handle_logout(request: service_pb2.LogoutRequest):
    access_token = request.access_token
    
    try:
        # 1. Decode Access Token (even if expired, we want the user_id)
        # We use verify_signature=False if we want to allow logout of expired tokens,
        # but the prompt implies a valid logout flow.
        # Actually, if the token is expired, the user is technically logged out from AT perspective,
        # but we want to clear the RT and Redis.
        
        payload = jwt.decode(access_token, JWT_SECRET, algorithms=[JWT_ALGORITHM], options={"verify_exp": False})
        user_id = payload.get("sub")
        
        if not user_id:
            return service_pb2.LogoutResponse(
                success=False,
                message="Invalid token payload."
            )
            
        # 2. Clear Session from Redis and Refresh Token from DB
        await force_user_logout(user_id)
        
        return service_pb2.LogoutResponse(
            success=True,
            message="Logged out successfully from all devices."
        )
        
    except jwt.InvalidTokenError:
        return service_pb2.LogoutResponse(
            success=False,
            message="Invalid token."
        )
    except Exception as e:
        print(f"Error in handle_logout: {str(e)}")
        return service_pb2.LogoutResponse(
            success=False,
            message=f"Logout failed: {str(e)}"
        )
