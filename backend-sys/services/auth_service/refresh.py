import jwt
import redis.asyncio as redis
from datetime import datetime, timezone, timedelta
from sqlalchemy import select, delete
from shared.database.engine import SessionLocal
from shared.database.schema import User, RefreshToken
from shared.proto import service_pb2
from shared.config import JWT_SECRET, JWT_ALGORITHM, REDIS_URL, REFRESH_TOKEN_EXPIRE_DAYS
from services.auth_service.auth_utils import create_access_token, create_refresh_token
from services.auth_service.audit_utils import log_audit_event
from shared.database.schema.audit_logs import AuditEventType

async def force_user_logout(user_id: str):
    """Utility to wipe user session from Redis and DB."""
    try:
        # 1. Clear Redis
        redis_kwargs = {"decode_responses": True}
        if REDIS_URL.startswith("rediss://"):
            redis_kwargs["ssl_cert_reqs"] = "none"
        redis_client = redis.from_url(REDIS_URL, **redis_kwargs)
        await redis_client.delete(f"user_session:{user_id}")
        await redis_client.close()
        
        # 2. Clear DB (any existing RT for this user)
        async with SessionLocal() as session:
            await session.execute(delete(RefreshToken).where(RefreshToken.user_id == user_id))
            await session.commit()
    except Exception as e:
        print(f"Error during force_user_logout: {str(e)}")

async def handle_refresh_token(request: service_pb2.RefreshTokenRequest):
    refresh_token_str = request.refresh_token
    
    try:
        # 1. Decode Refresh Token to get user_id (sub)
        payload = jwt.decode(refresh_token_str, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        user_id = payload.get("sub")
        
        if not user_id:
            return service_pb2.RefreshTokenResponse(
                success=False,
                message="Invalid refresh token payload."
            )
            
        async with SessionLocal() as session:
            # 2. Look up the token in the database
            stmt = select(RefreshToken).where(
                RefreshToken.user_id == user_id,
                RefreshToken.token_hash == refresh_token_str
            )
            result = await session.execute(stmt)
            db_rt = result.scalar_one_or_none()
            
            if not db_rt:
                return service_pb2.RefreshTokenResponse(
                    success=False,
                    message="Refresh token not found."
                )
            
            # 3. Check if revoked or expired
            if db_rt.revoked:
                await force_user_logout(user_id)
                return service_pb2.RefreshTokenResponse(
                    success=False,
                    message="Refresh token has been revoked. Logged out."
                )
            
            # Ensure naive comparison since expire_at is TIMESTAMP WITHOUT TIME ZONE
            now_naive = datetime.now(timezone.utc).replace(tzinfo=None)
            
            # Cleanup: Delete all expired tokens in the database
            cleanup_stmt = delete(RefreshToken).where(RefreshToken.expire_at < now_naive)
            await session.execute(cleanup_stmt)
            await session.commit()

            # Re-check if our specific token was just deleted or is expired
            if db_rt.expire_at < now_naive:
                await force_user_logout(user_id)
                return service_pb2.RefreshTokenResponse(
                    success=False,
                    message="Refresh token has expired. Logged out."
                )
            
            # 4. Fetch User details to generate new Access Token
            user_stmt = select(User).where(User.id == user_id)
            user_result = await session.execute(user_stmt)
            user = user_result.scalar_one_or_none()
            
            if not user or not user.is_active:
                return service_pb2.RefreshTokenResponse(
                    success=False,
                    message="User not found or inactive."
                )
            
            # 5. Generate New Access Token and ROTATE Refresh Token
            access_token = create_access_token({
                "sub": str(user.id),
                "org": str(user.organization_id),
                "role": user.role.value
            })
            new_refresh_token_str = create_refresh_token({"sub": str(user.id)})
            
            # 6. Update Refresh Token in DB (Rotation)
            expire_at = (datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)).replace(tzinfo=None)
            db_rt.token_hash = new_refresh_token_str
            db_rt.expire_at = expire_at
            db_rt.created_at = datetime.now(timezone.utc).replace(tzinfo=None) # Reset creation time for rotation
            
            await session.commit()
            
            # 7. Audit Log
            await log_audit_event(
                event_type=AuditEventType.TOKEN_REFRESH,
                user_id=user.id,
                organization_id=user.organization_id,
                ip_address=request.ip_address,
                user_agent=request.user_agent
            )
            
            return service_pb2.RefreshTokenResponse(
                success=True,
                access_token=access_token,
                refresh_token=new_refresh_token_str,
                user_id=str(user.id),
                organization_id=str(user.organization_id),
                message="Token refreshed successfully."
            )
            
    except jwt.ExpiredSignatureError:
        # Try to get user_id even if expired for cleanup
        try:
            payload = jwt.decode(refresh_token_str, JWT_SECRET, algorithms=[JWT_ALGORITHM], options={"verify_signature": False})
            u_id = payload.get("sub")
            if u_id:
                await force_user_logout(u_id)
        except:
            pass
        return service_pb2.RefreshTokenResponse(success=False, message="Refresh token expired. Logged out.")
    except jwt.InvalidTokenError:
        return service_pb2.RefreshTokenResponse(success=False, message="Invalid refresh token.")
    except Exception as e:
        print(f"Error in handle_refresh_token: {str(e)}")
        import traceback
        traceback.print_exc()
        return service_pb2.RefreshTokenResponse(success=False, message="Internal server error.")
