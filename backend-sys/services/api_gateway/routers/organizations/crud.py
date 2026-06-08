import re
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from uuid import UUID
from shared.database.schema import Organization, User
from services.api_gateway.routers.organizations.schemas import OrganizationUpdate
from typing import Optional, List

def slugify(text: str) -> str:
    """Helper to convert string into a URL-friendly slug."""
    text = text.lower().strip()
    text = re.sub(r'[^a-z0-9\s-]', '', text)
    text = re.sub(r'[\s-]+', '-', text)
    return text

class OrganizationCRUD:
    @staticmethod
    async def get_organization(db: AsyncSession, org_id: UUID) -> Optional[Organization]:
        """
        Retrieve organization details by ID.
        """
        stmt = select(Organization).where(Organization.id == org_id)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def update_organization(
        db: AsyncSession, 
        org_id: UUID, 
        data: OrganizationUpdate
    ) -> Optional[Organization]:
        """
        Update organization details, validating slug uniqueness.
        """
        organization = await OrganizationCRUD.get_organization(db, org_id)
        if not organization:
            return None

        # Check and update slug first if provided or changing name
        if data.slug is not None:
            formatted_slug = slugify(data.slug)
            if not formatted_slug:
                raise ValueError("Requested slug is invalid.")
            
            # Check for uniqueness
            stmt = select(Organization).where(Organization.slug == formatted_slug, Organization.id != org_id)
            res = await db.execute(stmt)
            existing = res.scalar_one_or_none()
            if existing:
                raise ValueError("Organization slug is already taken.")
            organization.slug = formatted_slug
        elif data.name is not None:
            # Dynamically update slug to match updated name if not manually specified
            new_slug = slugify(data.name)
            if new_slug:
                stmt = select(Organization).where(Organization.slug == new_slug, Organization.id != org_id)
                res = await db.execute(stmt)
                existing = res.scalar_one_or_none()
                if not existing:
                    organization.slug = new_slug

        if data.name is not None:
            organization.name = data.name
        
        if data.is_active is not None:
            organization.is_active = data.is_active

        await db.commit()
        await db.refresh(organization)
        return organization

    @staticmethod
    async def deactivate_organization(
        db: AsyncSession, 
        org_id: UUID, 
        redis_client
    ) -> bool:
        """
        Soft-delete an organization by setting is_active = False,
        and immediately invalidates all active user sessions in Redis.
        """
        organization = await OrganizationCRUD.get_organization(db, org_id)
        if not organization:
            return False

        organization.is_active = False

        # Query all users belonging to this organization to clear their sessions
        user_stmt = select(User).where(User.organization_id == org_id)
        user_res = await db.execute(user_stmt)
        users = user_res.scalars().all()

        # Invalidate active user sessions and auth caches in Redis
        keys_to_delete = []
        for user in users:
            keys_to_delete.append(f"user_session:{user.id}")
            keys_to_delete.append(f"user_auth_cache:{user.email}")

        if keys_to_delete and redis_client:
            try:
                await redis_client.delete(*keys_to_delete)
            except Exception as re_err:
                print(f"Redis session cleanup warning: {re_err}")

        await db.commit()
        return True
