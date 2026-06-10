from fastapi import APIRouter, Request, HTTPException, status, Depends, Cookie
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from uuid import UUID
from shared.proto import service_pb2
from shared.utils import get_db
from shared.database.schema import Team, TeamMember

router = APIRouter(prefix="/auth", tags=["Authentication"])

async def get_user_permissions(db: AsyncSession, user_id_str: str, role: str) -> list[str]:
    role = role.upper()
    all_permissions = ["products", "orders", "tickets", "connectors", "ai_config", "chats", "teams", "analytics", "internal_chat:request_customer", "chat:claim", "chat:read", "chat:request_handoff", "chat:grant_handoff", "chat:view_handled"]
    if role == "OWNER":
        return all_permissions
    
    try:
        user_id = UUID(user_id_str)
        stmt = (
            select(Team.permissions)
            .join(TeamMember, TeamMember.team_id == Team.id)
            .where(TeamMember.user_id == user_id)
        )
        res = await db.execute(stmt)
        permissions = res.scalar_one_or_none() or []
        
        # Ensure we can mutate the list and append sub-permissions if "chats" is present
        permissions_list = list(permissions)
        if "chats" in permissions_list:
            chat_sub_perms = [
                "chat:claim", 
                "chat:read", 
                "chat:request_handoff", 
                "chat:grant_handoff", 
                "chat:view_handled", 
                "internal_chat:request_customer"
            ]
            for perm in chat_sub_perms:
                if perm not in permissions_list:
                    permissions_list.append(perm)
                    
        return permissions_list
    except Exception as e:
        print(f"Error querying permissions for user {user_id_str}: {e}")
        return []

async def get_current_user(
    request: Request,
    access_token: Optional[str] = Cookie(None),
    db: AsyncSession = Depends(get_db)
):
    """
    FastAPI Dependency to verify the access token from cookies.
    It calls the AuthService.VerifyAccessToken gRPC method.
    """
    if not access_token:
        # Check if we have a refresh token to attempt a redirect/refresh
        if request.cookies.get("refresh_token"):
            raise HTTPException(
                status_code=status.HTTP_307_TEMPORARY_REDIRECT,
                headers={"Location": "/auth/refresh_token"}
            )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication token missing. Please log in."
        )
    
    auth_stub = request.app.state.auth_stub
    
    try:
        # Call gRPC AuthService.VerifyAccessToken
        grpc_request = service_pb2.VerifyAccessTokenRequest(access_token=access_token)
        grpc_response = await auth_stub.VerifyAccessToken(grpc_request)
        
        if not grpc_response.valid:
            if request.cookies.get("refresh_token"):
                raise HTTPException(
                    status_code=status.HTTP_307_TEMPORARY_REDIRECT,
                    headers={"Location": "/auth/refresh_token"}
                )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=grpc_response.message or "Invalid or expired session."
            )
            
        role = grpc_response.role
        permissions = await get_user_permissions(db, grpc_response.user_id, role)
        
        return {
            "user_id": grpc_response.user_id,
            "organization_id": grpc_response.organization_id,
            "organization_name": grpc_response.organization_name,
            "role": role,
            "permissions": permissions
        }
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        
        # Log error for internal tracking
        print(f"Error in get_current_user dependency: {str(e)}")
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while verifying your session."
        )

@router.get("/me")
async def read_users_me(current_user: dict = Depends(get_current_user)):
    """
    Endpoint to retrieve the current logged-in user's details.
    Uses get_current_user as a dependency.
    """
    return {
        "success": True,
        "user": current_user
    }
