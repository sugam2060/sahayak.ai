"""
AccountService: Efficient, class-based service for all account management operations.

Design principles:
- All DB queries target indexed columns (users.id, users.email).
- Redis session cache (`user_session:{user_id}`) is invalidated after any mutation so
  the next token verification re-fetches fresh data from the database.
- Email change uses a short-lived Redis token (24h TTL) keyed as
  `email_change:{token}` with value `{user_id}:{new_email}`.
"""
import asyncio
import secrets
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from shared.auth_utils import hash_password, verify_password
from shared.config import FRONTEND_URL, BACKEND_URL
from shared.database.schema.users import User
from shared.kafka_producer import KafkaProducerPool
from shared.redis_pool import RedisPool


class AccountService:
    # ------------------------------------------------------------------ #
    # Profile                                                               #
    # ------------------------------------------------------------------ #
    @staticmethod
    async def get_profile(db: AsyncSession, user_id: str) -> User:
        """
        Fetch the user's profile from the database using the primary-key index.
        Only selects the columns we actually need.
        """
        stmt = select(User).where(User.id == UUID(user_id))
        result = await db.execute(stmt)
        user = result.scalar_one_or_none()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User profile not found.",
            )
        return user

    # ------------------------------------------------------------------ #
    # Update Name                                                           #
    # ------------------------------------------------------------------ #
    @staticmethod
    async def update_name(db: AsyncSession, user_id: str, new_name: str) -> None:
        """Update the user's display name and invalidate their Redis session."""
        stmt = (
            update(User)
            .where(User.id == UUID(user_id))
            .values(full_name=new_name)
        )
        await db.execute(stmt)
        await db.commit()

        # Invalidate cached session so next token check loads fresh name
        await AccountService._invalidate_session(user_id)

    # ------------------------------------------------------------------ #
    # Change Password                                                        #
    # ------------------------------------------------------------------ #
    @staticmethod
    async def update_password(
        db: AsyncSession,
        user_id: str,
        current_password: str,
        new_password: str,
    ) -> None:
        """
        Verify current password then replace it with the hashed new one.
        Invalidates the Redis session on success to force re-auth.
        """
        # 1. Fetch current hash (single row, PK lookup)
        stmt = select(User.password_hash).where(User.id == UUID(user_id))
        result = await db.execute(stmt)
        row = result.one_or_none()
        if not row:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found.",
            )

        if not verify_password(current_password, row[0]):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Current password is incorrect.",
            )

        # 2. Update hash
        new_hash = hash_password(new_password)
        stmt = (
            update(User)
            .where(User.id == UUID(user_id))
            .values(password_hash=new_hash)
        )
        await db.execute(stmt)
        await db.commit()

        # 3. Invalidate session
        await AccountService._invalidate_session(user_id)

    # ------------------------------------------------------------------ #
    # Email Change — Request                                                 #
    # ------------------------------------------------------------------ #
    @staticmethod
    async def request_email_change(
        db: AsyncSession,
        user_id: str,
        new_email: str,
        full_name: str,
    ) -> None:
        """
        1. Check the requested email is not already taken.
        2. Store a time-limited Redis token.
        3. Send a verification email via Kafka.
        """
        # 1. Uniqueness check (email has a unique index)
        stmt = select(User.id).where(User.email == new_email)
        result = await db.execute(stmt)
        if result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This email address is already in use by another account.",
            )

        # 2. Generate a cryptographically-secure token and store in Redis
        token = secrets.token_urlsafe(32)
        redis_client = RedisPool.get_client()
        token_key = f"email_change:{token}"
        token_value = f"{user_id}:{new_email}"
        await redis_client.setex(token_key, 86400, token_value)  # 24h TTL

        # 3. Build and send email via Kafka
        template_path = Path(__file__).parent.parent.parent.parent / "auth_service" / "templates" / "email_change_email.html"
        with open(template_path, "r") as f:
            template_content = f.read()

        confirm_link = f"{FRONTEND_URL}/verify/email/{token}"
        html_content = (
            template_content
            .replace("{{full_name}}", full_name)
            .replace("{{new_email}}", new_email)
            .replace("{{verify_link}}", confirm_link)
        )

        await KafkaProducerPool.send_message(
            topic="mail-events",
            value={
                "email": new_email,
                "subject": "Confirm Your New Email Address — Sahayak",
                "html_content": html_content,
            },
        )

    # ------------------------------------------------------------------ #
    # Email Change — Confirm                                                 #
    # ------------------------------------------------------------------ #
    @staticmethod
    async def confirm_email_change(db: AsyncSession, token: str) -> str:
        """
        Validate the token from Redis, update the email in the DB,
        clean up the Redis key, and invalidate the session.
        Returns the user_id on success.
        """
        redis_client = RedisPool.get_client()
        token_key = f"email_change:{token}"
        value = await redis_client.get(token_key)

        if not value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This email change link is invalid or has expired.",
            )

        # value is bytes from Redis
        if isinstance(value, bytes):
            value = value.decode()

        user_id_str, new_email = value.split(":", 1)

        # Query old email from DB before updating
        stmt_old = select(User.email).where(User.id == UUID(user_id_str))
        res_old = await db.execute(stmt_old)
        old_email = res_old.scalar_one_or_none()

        # Update DB atomically
        stmt = (
            update(User)
            .where(User.id == UUID(user_id_str))
            .values(email=new_email, is_verified=True)
        )
        await db.execute(stmt)
        await db.commit()

        # Parallel cleanup: delete token + invalidate session + delete user_auth_cache
        cleanup_tasks = [
            redis_client.delete(token_key),
            AccountService._invalidate_session(user_id_str),
        ]
        if old_email:
            cleanup_tasks.append(redis_client.delete(f"user_auth_cache:{old_email}"))

        await asyncio.gather(*cleanup_tasks)

        return user_id_str

    # ------------------------------------------------------------------ #
    # Helpers                                                               #
    # ------------------------------------------------------------------ #
    @staticmethod
    async def _invalidate_session(user_id: str) -> None:
        """Remove the cached session from Redis so fresh data is loaded on next request."""
        try:
            redis_client = RedisPool.get_client()
            await redis_client.delete(f"user_session:{user_id}")
        except Exception:
            # Non-fatal; the DB remains the source of truth
            pass
