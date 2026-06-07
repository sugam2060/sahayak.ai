from pydantic import BaseModel, Field, EmailStr, ConfigDict
from typing import Optional, List
from uuid import UUID

class TeamCreate(BaseModel):
    team_name: str = Field(..., max_length=255)
    description: Optional[str] = None
    role: str = Field(default="AGENT", max_length=100)
    permissions: List[str] = []

class TeamUpdate(BaseModel):
    team_name: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = None
    role: Optional[str] = Field(None, max_length=100)
    permissions: Optional[List[str]] = None

class InviteMemberRequest(BaseModel):
    full_name: str = Field(..., max_length=255)
    email: EmailStr
    password: str = Field(..., min_length=6, max_length=255)
    role: str = Field(default="AGENT")
    team_id: Optional[UUID] = None

class TeamMemberResponse(BaseModel):
    user_id: UUID
    email: str
    full_name: str
    role: str
    is_active: bool

class TeamResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    organization_id: UUID
    team_name: str
    description: Optional[str] = None
    role: str
    permissions: List[str] = []
    created_at: str
    members: List[TeamMemberResponse] = []
