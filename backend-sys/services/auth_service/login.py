import uuid
import redis.asyncio as redis
import json
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from shared.database.engine import SessionLocal
from shared.database.schema import User, RefreshToken, Organization
from shared.proto import service_pb2
from shared.config import REDIS_URL, FRONTEND_URL
from services.auth_service.auth_utils import verify_password, create_access_token, create_refresh_token
from pathlib import Path
from datetime import datetime, timedelta, timezone
from shared.config import REFRESH_TOKEN_EXPIRE_DAYS
from services.auth_service.audit_utils import log_audit_event
from shared.database.schema.audit_logs import AuditEventType

import asyncio
from shared.redis_pool import RedisPool

async def handle_login(request: service_pb2.LoginRequest):
    try:
        redis_client = RedisPool.get_client()
        email_key = f"user_auth_cache:{request.email}"
        
        # 1. Try to get user from Redis cache first
        cached_user = await redis_client.get(email_key)
        user_data = None
        
        if cached_user:
            user_data = json.loads(cached_user)
        else:
            # 2. Fallback to Database
            async with SessionLocal() as session:
                stmt = select(User, Organization).join(
                    Organization, User.organization_id == Organization.id
                ).where(User.email == request.email)
                result = await session.execute(stmt)
                row = result.one_or_none()
                
                if not row:
                    return service_pb2.LoginResponse(success=False, message="Invalid email or password.")
                
                user, org = row
                if org.is_active is False:
                    return service_pb2.LoginResponse(success=False, message="Organization is inactive.")
                
                user_data = {
                    "id": str(user.id),
                    "full_name": user.full_name,
                    "email": user.email,
                    "password_hash": user.password_hash,
                    "role": user.role.value,
                    "organization_id": str(user.organization_id),
                    "organization_name": org.name,
                    "organization_slug": org.slug,
                    "is_verified": user.is_verified,
                    "is_active": user.is_active,
                    "failed_login_attempts": user.failed_login_attempts,
                    "locked_until": user.locked_until.isoformat() if user.locked_until else None
                }
                # Cache for 1 hour to keep it relatively fresh
                await redis_client.setex(email_key, 3600, json.dumps(user_data))

        # 3. Fast Lock Check (using cached or fresh data)
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        locked_until = None
        if user_data["locked_until"]:
            locked_until = datetime.fromisoformat(user_data["locked_until"]).replace(tzinfo=None)

        if locked_until and locked_until > now:
            lock_remaining = int((locked_until - now).total_seconds() / 60)
            return service_pb2.LoginResponse(
                success=False,
                message=f"Account temporarily locked. Try again in {lock_remaining} minutes."
            )
            
        # 4. Verify Password
        if not verify_password(request.password, user_data["password_hash"]):
            # For security-critical state like failed attempts, we MUST update the DB and invalidate cache
            async with SessionLocal() as session:
                async with session.begin():
                    # We need to re-fetch the user object to update it
                    stmt = select(User).where(User.id == uuid.UUID(user_data["id"]))
                    res = await session.execute(stmt)
                    user = res.scalar_one()
                    user.failed_login_attempts += 1
                    if user.failed_login_attempts >= 5:
                        user.locked_until = now + timedelta(minutes=15)
                    
                    # Invalidate cache so next attempt sees new failed_login_attempts/locked_until
                    await asyncio.gather(
                        session.commit(),
                        redis_client.delete(email_key)
                    )

            asyncio.create_task(log_audit_event(
                event_type=AuditEventType.LOGIN_FAILED,
                user_id=uuid.UUID(user_data["id"]),
                organization_id=uuid.UUID(user_data["organization_id"]),
                ip_address=request.ip_address,
                user_agent=request.user_agent,
                details={"reason": "Invalid password"}
            ))
            return service_pb2.LoginResponse(success=False, message="Invalid email or password.")
        
        # 5. Check Verification Status
        if not user_data["is_verified"]:
            # Check for existing verification token in Redis
            found_token = await redis_client.get(f"verify_user_token:{user_data['email']}")
            if found_token:
                return service_pb2.LoginResponse(
                    success=False, message="Please verify your email. Link already sent.", is_verified=False
                )
            else:
                # Resend logic...
                verification_token = str(uuid.uuid4())
                await asyncio.gather(
                    redis_client.setex(f"verify_user:{verification_token}", 86400, user_data['email']),
                    redis_client.setex(f"verify_user_token:{user_data['email']}", 86400, verification_token)
                )
                
                # Send Verification Email (Background Task)
                template_path = Path(__file__).parent / "templates" / "verification_email.html"
                with open(template_path, "r") as f:
                    template_content = f.read()
                
                verify_link = f"{FRONTEND_URL}/verify/user/{verification_token}"
                html_content = template_content.replace("{{full_name}}", user_data['full_name']).replace("{{verify_link}}", verify_link)
                
                from shared.kafka_producer import KafkaProducerPool
                await KafkaProducerPool.send_message(
                    topic="mail-events",
                    value={
                        "email": user_data['email'],
                        "subject": "Verify your Sahayak Account",
                        "html_content": html_content
                    }
                )
                return service_pb2.LoginResponse(
                    success=False, message="Your email is not verified. New link sent.", is_verified=False
                )

        # 6. Success Login Path - Token Generation
        user_id_obj = uuid.UUID(user_data["id"])
        org_id_obj = uuid.UUID(user_data["organization_id"])
        
        access_token = create_access_token({
            "sub": user_data["id"], 
            "org": user_data["organization_id"], 
            "role": user_data["role"]
        })
        refresh_token_str = create_refresh_token({"sub": user_data["id"]})
        
        # 7. Finalize Session (Parallel DB and Redis)
        expire_at = (datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)).replace(tzinfo=None)
        
        async with SessionLocal() as session:
            async with session.begin():
                # Update User metadata
                user_stmt = select(User).where(User.id == user_id_obj)
                user_res = await session.execute(user_stmt)
                user = user_res.scalar_one()
                user.failed_login_attempts = 0
                user.locked_until = None
                user.last_login_at = datetime.now(timezone.utc)

                # Refresh Token Rotation
                rt_stmt = select(RefreshToken).where(RefreshToken.user_id == user_id_obj)
                rt_result = await session.execute(rt_stmt)
                db_rt = rt_result.scalar_one_or_none()
                
                if db_rt:
                    db_rt.token_hash = refresh_token_str 
                    db_rt.expire_at = expire_at
                    db_rt.revoked = False
                else:
                    session.add(RefreshToken(
                        user_id=user_id_obj, organization_id=org_id_obj,
                        token_hash=refresh_token_str, expire_at=expire_at
                    ))

                # Redis caching for both auth and session
                session_payload = {
                    "user_id": user_data["id"], "full_name": user_data["full_name"], "role": user_data["role"],
                    "organization_id": user_data["organization_id"], 
                    "organization_name": user_data["organization_name"], 
                    "organization_slug": user_data["organization_slug"]
                }
                
                await asyncio.gather(
                    session.commit(),
                    redis_client.setex(
                        f"user_session:{user_data['id']}",
                        REFRESH_TOKEN_EXPIRE_DAYS * 24 * 3600,
                        json.dumps(session_payload)
                    ),
                    # Also update/refresh the auth cache
                    redis_client.setex(email_key, 3600, json.dumps(user_data))
                )
        
        # 8. Background Audit
        asyncio.create_task(log_audit_event(
            event_type=AuditEventType.LOGIN_SUCCESS,
            user_id=user_id_obj, organization_id=org_id_obj,
            ip_address=request.ip_address, user_agent=request.user_agent
        ))
        
        return service_pb2.LoginResponse(
            success=True,
            message="Login successful.",
            access_token=access_token,
            refresh_token=refresh_token_str,
            user_id=user_data["id"],
            organization_id=user_data["organization_id"],
            is_verified=True,
            full_name=user_data["full_name"],
            organization_name=user_data["organization_name"],
            organization_slug=user_data["organization_slug"],
            email=user_data["email"]
        )
    except Exception as e:
        print(f"ERROR in handle_login: {str(e)}")
        import traceback
        traceback.print_exc()
        return service_pb2.LoginResponse(success=False, message="Internal server error.")
