import json
import redis.asyncio as redis
from sqlalchemy import select
from shared.database.engine import SessionLocal
from shared.database.schema import User, Organization
from shared.proto import service_pb2
from shared.config import REDIS_URL, REFRESH_TOKEN_EXPIRE_DAYS
from services.auth_service.auth_utils import decode_access_token

async def handle_verify_access_token(request: service_pb2.VerifyAccessTokenRequest):
    token = request.access_token
    
    # 1. Decode Token
    payload = decode_access_token(token)
    if not payload:
        return service_pb2.VerifyAccessTokenResponse(
            valid=False,
            message="Invalid or expired access token."
        )
    
    user_id = payload.get("sub")
    if not user_id:
        return service_pb2.VerifyAccessTokenResponse(
            valid=False,
            message="Token payload is missing user identification."
        )
    
    # 2. Check Redis for User Session
    try:
        from shared.redis_pool import RedisPool
        redis_client = RedisPool.get_client()
        
        session_json = await redis_client.get(f"user_session:{user_id}")
        if not session_json:
            # Fallback to Database if Redis session is missing
            async with SessionLocal() as session:
                stmt = select(User, Organization).join(Organization, User.organization_id == Organization.id).where(User.id == user_id)
                db_result = await session.execute(stmt)
                row = db_result.one_or_none()
                
                if not row:
                    return service_pb2.VerifyAccessTokenResponse(
                        valid=False,
                        message="User not found. Please log in again."
                    )
                
                user, org = row
                
                # Verify user and organization are active
                if not user.is_active or not user.is_verified or org.is_active is False:
                    return service_pb2.VerifyAccessTokenResponse(
                        valid=False,
                        message="Account or organization is inactive."
                    )
                
                # Re-cache in Redis
                session_data = {
                    "user_id": str(user.id),
                    "full_name": user.full_name,
                    "role": user.role.value,
                    "organization_id": str(org.id),
                    "organization_name": org.name,
                    "organization_slug": org.slug
                }
                session_json = json.dumps(session_data)
                await redis_client.setex(
                    f"user_session:{user_id}",
                    REFRESH_TOKEN_EXPIRE_DAYS * 24 * 3600,
                    session_json
                )
        
        # 3. Parse and Return Details
        session_data = json.loads(session_json)
        return service_pb2.VerifyAccessTokenResponse(
            valid=True,
            user_id=session_data["user_id"],
            full_name=session_data["full_name"],
            organization_id=session_data["organization_id"],
            organization_name=session_data["organization_name"],
            organization_slug=session_data["organization_slug"],
            role=session_data["role"],
            message="Token verified successfully."
        )
    except Exception as e:
        print(f"Error in token verification: {str(e)}")
        return service_pb2.VerifyAccessTokenResponse(
            valid=False,
            message=f"Internal error during token verification: {str(e)}"
        )
