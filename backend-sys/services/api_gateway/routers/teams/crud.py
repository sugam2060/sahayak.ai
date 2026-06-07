from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from uuid import UUID
from shared.database.schema import Team, TeamMember, User
from services.api_gateway.routers.teams.schemas import TeamCreate, TeamUpdate
from typing import List, Optional

class TeamCRUD:
    @staticmethod
    async def get_teams(db: AsyncSession, org_id: UUID) -> List[Team]:
        """
        Retrieve all teams for the organization, preloading their members and user details.
        """
        stmt = (
            select(Team)
            .where(Team.organization_id == org_id)
            .options(
                selectinload(Team.members).selectinload(TeamMember.user)
            )
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def get_team_by_id(db: AsyncSession, team_id: UUID, org_id: UUID) -> Optional[Team]:
        """
        Retrieve a single team by ID within the organization.
        """
        stmt = (
            select(Team)
            .where(Team.id == team_id, Team.organization_id == org_id)
            .options(
                selectinload(Team.members).selectinload(TeamMember.user)
            )
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def create_team(db: AsyncSession, org_id: UUID, data: TeamCreate) -> Team:
        """
        Create a new team in the database.
        """
        new_team = Team(
            organization_id=org_id,
            team_name=data.team_name,
            description=data.description,
            role=data.role,
            permissions=data.permissions
        )
        db.add(new_team)
        await db.commit()
        await db.refresh(new_team)
        return new_team

    @staticmethod
    async def update_team(db: AsyncSession, team_id: UUID, org_id: UUID, data: TeamUpdate) -> Optional[Team]:
        """
        Update an existing team.
        """
        team = await TeamCRUD.get_team_by_id(db, team_id, org_id)
        if not team:
            return None
        
        if data.team_name is not None:
            team.team_name = data.team_name
        if data.description is not None:
            team.description = data.description
        if data.role is not None:
            team.role = data.role
        if data.permissions is not None:
            team.permissions = data.permissions
            
        await db.commit()
        await db.refresh(team)
        return team

    @staticmethod
    async def delete_team(db: AsyncSession, team_id: UUID, org_id: UUID) -> bool:
        """
        Delete a team from the database.
        """
        team = await TeamCRUD.get_team_by_id(db, team_id, org_id)
        if not team:
            return False
            
        await db.delete(team)
        await db.commit()
        return True
