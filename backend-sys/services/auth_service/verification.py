import asyncio
import redis.asyncio as redis
from shared.database.engine import SessionLocal
from shared.database.schema import User
from shared.config import REDIS_URL
from shared.proto import service_pb2
from sqlalchemy import select, update

async def handle_verify_email(request: service_pb2.VerifyEmailRequest):
    """
    Handles email verification by checking the token in Redis.
    """
    token = request.token
    from shared.redis_pool import RedisPool
    redis_client = RedisPool.get_client()
    
    try:
        # 1. Lookup email in Redis
        email = await redis_client.get(f"verify_user:{token}")
        
        if not email:
            return service_pb2.VerifyEmailResponse(
                success=False,
                message="Invalid or expired verification token."
            )
            
        # 2. Update User in Database
        async with SessionLocal() as session:
            async with session.begin():
                stmt = (
                    update(User)
                    .where(User.email == email)
                    .values(is_verified=True, is_active=True)
                )
                await session.execute(stmt)
        
        # 3. Cleanup: Remove both tokens from Redis in parallel
        await asyncio.gather(
            redis_client.delete(f"verify_user:{token}"),
            redis_client.delete(f"verify_user_token:{email}")
        )
        
        return service_pb2.VerifyEmailResponse(
            success=True,
            message="Email verified successfully. You can now log in."
        )
        
    except Exception as e:
        print(f"Error during email verification: {str(e)}")
        import traceback
        traceback.print_exc()
        return service_pb2.VerifyEmailResponse(
            success=False,
            message="An internal error occurred during verification. Please try again later."
        )
