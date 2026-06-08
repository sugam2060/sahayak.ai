from pydantic import BaseModel, Field, ConfigDict
from typing import Optional
from uuid import UUID
from datetime import datetime

class OrganizationUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=255)
    slug: Optional[str] = Field(None, max_length=100)
    is_active: Optional[bool] = None

class OrganizationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    slug: str
    plan: str  # Will serialize PlanType enum as string
    is_active: bool
    owner_id: Optional[UUID] = None
    created_at: datetime
    updated_at: datetime
