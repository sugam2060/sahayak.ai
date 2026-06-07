import uuid
import asyncio
from pathlib import Path
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from uuid import UUID
from shared.database.schema import Team, TeamMember, User, UserRole
from services.api_gateway.routers.teams.schemas import InviteMemberRequest
from services.auth_service.auth_utils import hash_password
from shared.config import FRONTEND_URL
from shared.kafka_producer import KafkaProducerPool
from typing import List, Optional

class TeamMemberManager:
    @staticmethod
    async def assign_member(db: AsyncSession, team_id: UUID, user_id: UUID, org_id: UUID) -> bool:
        """
        Assigns a user to a team. If the user is already assigned to a team,
        their existing membership is removed first, enforcing the single-team rule.
        """
        # Verify team exists in the caller's organization
        team_stmt = select(Team).where(Team.id == team_id, Team.organization_id == org_id)
        team_res = await db.execute(team_stmt)
        team = team_res.scalar_one_or_none()
        if not team:
            raise ValueError("Team not found in your organization.")

        # Verify user exists in the caller's organization
        user_stmt = select(User).where(User.id == user_id, User.organization_id == org_id)
        user_res = await db.execute(user_stmt)
        user = user_res.scalar_one_or_none()
        if not user:
            raise ValueError("User not found in your organization.")

        # Enforce single team constraint: remove existing membership
        del_stmt = delete(TeamMember).where(TeamMember.user_id == user_id)
        await db.execute(del_stmt)

        # Create new membership
        new_membership = TeamMember(
            user_id=user_id,
            team_id=team_id,
            role="member"
        )
        db.add(new_membership)
        await db.commit()
        return True

    @staticmethod
    async def remove_member(db: AsyncSession, team_id: UUID, user_id: UUID, org_id: UUID) -> bool:
        """
        Removes a member from a team.
        """
        # Verify team belongs to the organization
        team_stmt = select(Team).where(Team.id == team_id, Team.organization_id == org_id)
        team_res = await db.execute(team_stmt)
        if not team_res.scalar_one_or_none():
            raise ValueError("Team not found in your organization.")

        # Delete the membership
        stmt = delete(TeamMember).where(TeamMember.team_id == team_id, TeamMember.user_id == user_id)
        res = await db.execute(stmt)
        await db.commit()
        return res.rowcount > 0

    @staticmethod
    async def get_unassigned_members(db: AsyncSession, org_id: UUID) -> List[User]:
        """
        Retrieves all active users in the organization who are not assigned to any team.
        """
        # Get user_ids of all assigned members
        assigned_stmt = select(TeamMember.user_id)
        assigned_res = await db.execute(assigned_stmt)
        assigned_user_ids = [row[0] for row in assigned_res.fetchall()]

        # Query active users in the org not in the assigned list
        stmt = (
            select(User)
            .where(
                User.organization_id == org_id,
                User.is_active == True,
                ~User.id.in_(assigned_user_ids) if assigned_user_ids else True
            )
        )
        res = await db.execute(stmt)
        return list(res.scalars().all())

    @staticmethod
    async def invite_member(
        db: AsyncSession,
        redis_client,
        org_id: UUID,
        data: InviteMemberRequest
    ) -> User:
        """
        Invites a new team member by creating a user account (is_active=False),
        generating a verification token in Redis, and sending an invite email via Kafka.
        """
        # Check if email already registered
        email_stmt = select(User).where(User.email == data.email)
        email_res = await db.execute(email_stmt)
        if email_res.scalar_one_or_none():
            raise ValueError(f"The email '{data.email}' is already registered.")

        # Determine target user role from string
        try:
            target_role = UserRole(data.role.upper())
        except ValueError:
            target_role = UserRole.AGENT

        if target_role == UserRole.OWNER:
            raise ValueError("Cannot invite another user as OWNER.")

        # Create new User
        new_user = User(
            full_name=data.full_name,
            email=data.email,
            password_hash=hash_password(data.password),
            role=target_role,
            organization_id=org_id,
            is_verified=False,
            is_active=False  # Must verify email to activate
        )
        db.add(new_user)
        await db.flush() # Populate user ID

        # Optional Team assignment
        if data.team_id:
            # Verify team exists in organization
            team_stmt = select(Team).where(Team.id == data.team_id, Team.organization_id == org_id)
            team_res = await db.execute(team_stmt)
            if not team_res.scalar_one_or_none():
                raise ValueError("Team not found in your organization.")

            new_membership = TeamMember(
                user_id=new_user.id,
                team_id=data.team_id,
                role="member"
            )
            db.add(new_membership)

        # Generate verification token
        verification_token = str(uuid.uuid4())
        await asyncio.gather(
            redis_client.setex(f"verify_user:{verification_token}", 86400, new_user.email),
            redis_client.setex(f"verify_user_token:{new_user.email}", 86400, verification_token)
        )

        # Fetch organization to get the organization name
        from shared.database.schema.organizations import Organization
        org_stmt = select(Organization).where(Organization.id == org_id)
        org_res = await db.execute(org_stmt)
        org = org_res.scalar_one_or_none()
        org_name = org.name if org else "Sahayak Workspace"

        # Load invitation template
        template_path = Path(__file__).parents[3] / "auth_service" / "templates" / "invitation_email.html"
        with open(template_path, "r") as f:
            template_content = f.read()

        verify_link = f"{FRONTEND_URL}/verify/user/{verification_token}"
        html_content = (
            template_content
            .replace("{{full_name}}", new_user.full_name)
            .replace("{{email}}", new_user.email)
            .replace("{{org_name}}", org_name)
            .replace("{{temporary_password}}", data.password)
            .replace("{{verify_link}}", verify_link)
        )

        # Publish invite mail to Kafka
        await KafkaProducerPool.send_message(
            topic="mail-events",
            value={
                "email": new_user.email,
                "subject": f"You have been invited to join {org_name}",
                "html_content": html_content
            }
        )

        await db.commit()
        return new_user
