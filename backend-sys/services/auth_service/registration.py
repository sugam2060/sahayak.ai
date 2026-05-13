from passlib.context import CryptContext
from sqlalchemy.exc import IntegrityError
from shared.database.engine import SessionLocal
from shared.database.schema import Organization, User, UserRole
from shared.proto import service_pb2
import grpc
import uuid
import redis.asyncio as redis
from pathlib import Path
from shared.config import FRONTEND_URL, REDIS_URL

from services.auth_service.auth_utils import hash_password

async def handle_registration(request: service_pb2.RegisterRequest):
    async with SessionLocal() as session:
        async with session.begin():
            try:
                # 1. Create Organization
                new_org = Organization(
                    name=request.org_name,
                    slug=request.org_slug
                )
                session.add(new_org)
                
                # Flush to generate org ID
                await session.flush()
                
                # 2. Create Owner User
                verification_token = str(uuid.uuid4())
                new_user = User(
                    full_name=request.user_full_name,
                    email=request.user_email,
                    password_hash=hash_password(request.user_password),
                    role=UserRole.OWNER,
                    organization_id=new_org.id,
                    is_verified=False,
                    is_active=False  # Inactive until verified
                )
                session.add(new_user)
                
                # Flush to generate user ID
                await session.flush()
                
                # 3. Store verification token in Redis (TTL: 24 hours)
                redis_kwargs = {"decode_responses": True}
                if REDIS_URL.startswith("rediss://"):
                    redis_kwargs["ssl_cert_reqs"] = "none"
                
                redis_client = redis.from_url(REDIS_URL, **redis_kwargs)
                await redis_client.setex(
                    f"verify_user:{verification_token}",
                    86400,  # 24 hours
                    new_user.email
                )
                await redis_client.close()
                
                # 4. Link Owner back to Organization
                new_org.owner_id = new_user.id
                
                # 4. Send Verification Email (Background Task)
                template_path = Path(__file__).parent / "templates" / "verification_email.html"
                with open(template_path, "r") as f:
                    template_content = f.read()
                
                verify_link = f"{FRONTEND_URL}/verify/user/{verification_token}"
                html_content = template_content.replace("{{full_name}}", new_user.full_name).replace("{{verify_link}}", verify_link)
                
                from shared.mail_service import send_verification_email
                send_verification_email.delay(
                    email=new_user.email,
                    subject="Verify your Sahayak Account",
                    html_content=html_content
                )
                
                return service_pb2.RegisterResponse(
                    organization_id=str(new_org.id),
                    user_id=str(new_user.id),
                    message="Registration successful. Please check your email to verify your account."
                )
                
            except IntegrityError as e:
                await session.rollback()
                error_msg = str(e.orig)
                if "organizations_slug_key" in error_msg:
                    raise ValueError(f"The organization slug '{request.org_slug}' is already taken.")
                if "ix_users_email" in error_msg:
                    raise ValueError(f"The email '{request.user_email}' is already registered.")
                if "ix_unique_owner_per_org" in error_msg:
                    raise ValueError("This organization already has an owner.")
                raise ValueError("A database integrity error occurred. Please check your data.")
            except Exception as e:
                await session.rollback()
                raise e
