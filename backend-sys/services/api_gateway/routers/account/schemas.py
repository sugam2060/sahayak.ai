from pydantic import BaseModel, EmailStr, field_validator
from typing import Optional
from datetime import datetime


class UpdateNameRequest(BaseModel):
    full_name: str

    @field_validator("full_name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 2:
            raise ValueError("Full name must be at least 2 characters.")
        if len(v) > 255:
            raise ValueError("Full name must not exceed 255 characters.")
        return v


class UpdatePasswordRequest(BaseModel):
    current_password: str
    new_password: str
    confirm_password: str

    @field_validator("new_password")
    @classmethod
    def validate_new_password(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("New password must be at least 8 characters.")
        return v

    @field_validator("confirm_password")
    @classmethod
    def passwords_must_match(cls, v: str, info) -> str:
        if "new_password" in info.data and v != info.data["new_password"]:
            raise ValueError("Passwords do not match.")
        return v


class RequestEmailChangeRequest(BaseModel):
    new_email: EmailStr


class AccountProfileResponse(BaseModel):
    user_id: str
    full_name: str
    email: str
    role: str
    created_at: Optional[datetime] = None
    last_login_at: Optional[datetime] = None

    model_config = {"from_attributes": True}
