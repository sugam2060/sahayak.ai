from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from typing import List
from shared.utils import get_db
from shared.redis_pool import RedisPool
from services.api_gateway.routers.teams.permissions import check_permission
from services.api_gateway.routers.teams.schemas import (
    TeamCreate, TeamUpdate, TeamResponse, InviteMemberRequest, TeamMemberResponse
)
from services.api_gateway.routers.teams.crud import TeamCRUD
from services.api_gateway.routers.teams.members import TeamMemberManager

router = APIRouter(prefix="/api/teams", tags=["Team Management"])

def serialize_team(team) -> dict:
    """Helper to serialize a SQLAlchemy Team model to match TeamResponse schema."""
    return {
        "id": team.id,
        "organization_id": team.organization_id,
        "team_name": team.team_name,
        "description": team.description,
        "role": team.role,
        "permissions": team.permissions or [],
        "created_at": team.created_at.isoformat() if team.created_at else "",
        "members": [
            {
                "user_id": m.user.id,
                "email": m.user.email,
                "full_name": m.user.full_name,
                "role": m.user.role.value if hasattr(m.user.role, 'value') else str(m.user.role),
                "is_active": m.user.is_active
            } for m in team.members if m.user
        ]
    }

@router.get("", response_model=List[TeamResponse])
async def get_teams(
    current_user: dict = Depends(check_permission("teams")),
    db: AsyncSession = Depends(get_db)
):
    try:
        org_id = UUID(current_user["organization_id"])
        teams = await TeamCRUD.get_teams(db, org_id)
        return [serialize_team(t) for t in teams]
    except Exception as e:
        print(f"Error fetching teams: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve teams."
        )

@router.post("", response_model=TeamResponse, status_code=status.HTTP_201_CREATED)
async def create_team(
    data: TeamCreate,
    current_user: dict = Depends(check_permission("teams")),
    db: AsyncSession = Depends(get_db)
):
    try:
        org_id = UUID(current_user["organization_id"])
        new_team = await TeamCRUD.create_team(db, org_id, data)
        # Re-fetch to preload relationships
        fetched_team = await TeamCRUD.get_team_by_id(db, new_team.id, org_id)
        return serialize_team(fetched_team)
    except Exception as e:
        print(f"Error creating team: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create team."
        )

@router.get("/members/unassigned", response_model=List[TeamMemberResponse])
async def get_unassigned_members(
    current_user: dict = Depends(check_permission("teams")),
    db: AsyncSession = Depends(get_db)
):
    try:
        org_id = UUID(current_user["organization_id"])
        users = await TeamMemberManager.get_unassigned_members(db, org_id)
        return [
            {
                "user_id": u.id,
                "email": u.email,
                "full_name": u.full_name,
                "role": u.role.value if hasattr(u.role, 'value') else str(u.role),
                "is_active": u.is_active
            } for u in users
        ]
    except Exception as e:
        print(f"Error fetching unassigned members: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve unassigned members list."
        )

@router.get("/{team_id}", response_model=TeamResponse)
async def get_team_detail(
    team_id: UUID,
    current_user: dict = Depends(check_permission("teams")),
    db: AsyncSession = Depends(get_db)
):
    org_id = UUID(current_user["organization_id"])
    team = await TeamCRUD.get_team_by_id(db, team_id, org_id)
    if not team:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Team not found."
        )
    return serialize_team(team)

@router.put("/{team_id}", response_model=TeamResponse)
async def update_team(
    team_id: UUID,
    data: TeamUpdate,
    current_user: dict = Depends(check_permission("teams")),
    db: AsyncSession = Depends(get_db)
):
    try:
        org_id = UUID(current_user["organization_id"])
        team = await TeamCRUD.update_team(db, team_id, org_id, data)
        if not team:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Team not found."
            )
        return serialize_team(team)
    except HTTPException as he:
        raise he
    except Exception as e:
        print(f"Error updating team: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update team."
        )

@router.delete("/{team_id}")
async def delete_team(
    team_id: UUID,
    current_user: dict = Depends(check_permission("teams")),
    db: AsyncSession = Depends(get_db)
):
    try:
        org_id = UUID(current_user["organization_id"])
        success = await TeamCRUD.delete_team(db, team_id, org_id)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Team not found."
            )
        return {"success": True, "message": "Team deleted successfully."}
    except HTTPException as he:
        raise he
    except Exception as e:
        print(f"Error deleting team: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete team."
        )

@router.post("/{team_id}/members")
async def assign_team_member(
    team_id: UUID,
    payload: dict, # expecting {"user_id": str}
    current_user: dict = Depends(check_permission("teams")),
    db: AsyncSession = Depends(get_db)
):
    user_id_str = payload.get("user_id")
    if not user_id_str:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="user_id is required."
        )
    try:
        user_id = UUID(user_id_str)
        org_id = UUID(current_user["organization_id"])
        await TeamMemberManager.assign_member(db, team_id, user_id, org_id)
        return {"success": True, "message": "Member assigned to team successfully."}
    except ValueError as ve:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(ve)
        )
    except Exception as e:
        print(f"Error assigning team member: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to assign member to team."
        )

@router.delete("/{team_id}/members/{user_id}")
async def remove_team_member(
    team_id: UUID,
    user_id: UUID,
    current_user: dict = Depends(check_permission("teams")),
    db: AsyncSession = Depends(get_db)
):
    try:
        org_id = UUID(current_user["organization_id"])
        success = await TeamMemberManager.remove_member(db, team_id, user_id, org_id)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Member association not found in this team."
            )
        return {"success": True, "message": "Member removed from team successfully."}
    except ValueError as ve:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(ve)
        )
    except Exception as e:
        print(f"Error removing team member: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to remove member from team."
        )

@router.post("/invite")
async def invite_team_member(
    data: InviteMemberRequest,
    current_user: dict = Depends(check_permission("teams")),
    db: AsyncSession = Depends(get_db)
):
    try:
        org_id = UUID(current_user["organization_id"])
        redis_client = RedisPool.get_client()
        new_user = await TeamMemberManager.invite_member(
            db=db,
            redis_client=redis_client,
            org_id=org_id,
            data=data
        )
        return {
            "success": True,
            "message": "Team member invited successfully. A verification email has been sent.",
            "user_id": str(new_user.id)
        }
    except ValueError as ve:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(ve)
        )
    except Exception as e:
        print(f"Error inviting team member: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to invite team member."
        )
