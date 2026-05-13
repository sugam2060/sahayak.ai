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

async def handle_login(request: service_pb2.LoginRequest):
    try:
        async with SessionLocal() as session:
            async with session.begin():
                # 1. Find User and Organization
                stmt = select(User, Organization).join(Organization, User.organization_id == Organization.id).where(User.email == request.email)
                result = await session.execute(stmt)
                row = result.one_or_none()
                
                if not row:
                    return service_pb2.LoginResponse(
                        success=False,
                        message="Invalid email or password."
                    )
                
                user, org = row
                
                # 2. Check if account is locked
                now = datetime.now(timezone.utc).replace(tzinfo=None)
                if user.locked_until and user.locked_until > now:
                    lock_remaining = int((user.locked_until - now).total_seconds() / 60)
                    return service_pb2.LoginResponse(
                        success=False,
                        message=f"Account is temporarily locked due to multiple failed attempts. Please try again in {lock_remaining} minutes."
                    )
                    
                # 3. Verify Password
                if not verify_password(request.password, user.password_hash):
                    # Increment failed attempts
                    user.failed_login_attempts += 1
                    if user.failed_login_attempts >= 5:
                        user.locked_until = now + timedelta(minutes=15)
                        await log_audit_event(
                            event_type=AuditEventType.ACCOUNT_LOCKED,
                            user_id=user.id,
                            organization_id=user.organization_id,
                            ip_address=request.ip_address,
                            user_agent=request.user_agent,
                            details={"attempts": user.failed_login_attempts}
                        )
                    
                    await log_audit_event(
                        event_type=AuditEventType.LOGIN_FAILED,
                        user_id=user.id,
                        organization_id=user.organization_id,
                        ip_address=request.ip_address,
                        user_agent=request.user_agent,
                        details={"reason": "Invalid password"}
                    )
                    
                    return service_pb2.LoginResponse(
                        success=False,
                        message="Invalid email or password."
                    )
                
                # Reset failed attempts on successful password verification
                user.failed_login_attempts = 0
                user.locked_until = None
                user.last_login_at = datetime.now(timezone.utc)
                    
                # 3. Check Verification Status
                if not user.is_verified:
                    # Check Redis for existing token
                    redis_kwargs = {"decode_responses": True}
                    if REDIS_URL.startswith("rediss://"):
                        redis_kwargs["ssl_cert_reqs"] = "none"
                    
                    redis_client = redis.from_url(REDIS_URL, **redis_kwargs)
                    
                    found_token = None
                    async for key in redis_client.scan_iter("verify_user:*"):
                        val = await redis_client.get(key)
                        if val == user.email:
                            found_token = key.split(":")[1]
                            break
                    
                    if found_token:
                        await redis_client.close()
                        return service_pb2.LoginResponse(
                            success=False,
                            message="Please verify your email. A verification link was already sent.",
                            is_verified=False
                        )
                    else:
                        # Token not found, resend email
                        verification_token = str(uuid.uuid4())
                        await redis_client.setex(
                            f"verify_user:{verification_token}",
                            86400,  # 24 hours
                            user.email
                        )
                        await redis_client.close()
                        
                        # Send Verification Email
                        template_path = Path(__file__).parent / "templates" / "verification_email.html"
                        if template_path.exists():
                            with open(template_path, "r") as f:
                                template_content = f.read()
                            
                            verify_link = f"{FRONTEND_URL}/verify/user/{verification_token}"
                            html_content = template_content.replace("{{full_name}}", user.full_name).replace("{{verify_link}}", verify_link)
                            
                            from shared.mail_service import send_verification_email
                            send_verification_email.delay(
                                email=user.email,
                                subject="Verify your Sahayak Account",
                                html_content=html_content
                            )
                        
                        return service_pb2.LoginResponse(
                            success=False,
                            message="Your email is not verified. A new verification link has been sent to your email.",
                            is_verified=False
                        )

                # 4. Success Login - Generate Tokens
                access_token = create_access_token({"sub": str(user.id), "org": str(user.organization_id), "role": user.role.value})
                refresh_token_str = create_refresh_token({"sub": str(user.id)})
                
                # 5. Store/Update Refresh Token in Database
                rt_stmt = select(RefreshToken).where(RefreshToken.user_id == user.id)
                rt_result = await session.execute(rt_stmt)
                db_rt = rt_result.scalar_one_or_none()
                
                expire_at = (datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)).replace(tzinfo=None)
                
                if db_rt:
                    db_rt.token_hash = refresh_token_str 
                    db_rt.expire_at = expire_at
                    db_rt.revoked = False
                else:
                    new_rt = RefreshToken(
                        user_id=user.id,
                        organization_id=user.organization_id,
                        token_hash=refresh_token_str,
                        expire_at=expire_at
                    )
                    session.add(new_rt)
                
                # 6. Cache User Session in Redis for fast verification
                redis_kwargs = {"decode_responses": True}
                if REDIS_URL.startswith("rediss://"):
                    redis_kwargs["ssl_cert_reqs"] = "none"
                
                redis_client = redis.from_url(REDIS_URL, **redis_kwargs)
                session_data = {
                    "user_id": str(user.id),
                    "full_name": user.full_name,
                    "role": user.role.value,
                    "organization_id": str(org.id),
                    "organization_name": org.name,
                    "organization_slug": org.slug
                }
                await redis_client.setex(
                    f"user_session:{user.id}",
                    REFRESH_TOKEN_EXPIRE_DAYS * 24 * 3600,
                    json.dumps(session_data)
                )
                await redis_client.close()
            
                await log_audit_event(
                    event_type=AuditEventType.LOGIN_SUCCESS,
                    user_id=user.id,
                    organization_id=user.organization_id,
                    ip_address=request.ip_address,
                    user_agent=request.user_agent
                )
            
            return service_pb2.LoginResponse(
                success=True,
                message="Login successful.",
                access_token=access_token,
                refresh_token=refresh_token_str,
                user_id=str(user.id),
                organization_id=str(user.organization_id),
                is_verified=True
            )
    except Exception as e:
        print(f"ERROR in handle_login: {str(e)}")
        import traceback
        traceback.print_exc()
        return service_pb2.LoginResponse(
            success=False,
            message="An internal server error occurred. Please try again later."
        )
