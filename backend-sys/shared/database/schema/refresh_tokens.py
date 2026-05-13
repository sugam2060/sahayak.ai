from datetime import datetime
from uuid import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, Boolean, DateTime, ForeignKey, text
from shared.database.schema.base import Base

class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    # Composite Primary Key
    # user_id is unique to enforce 1:1 relationship with User
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True, unique=True)
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), primary_key=True)
    
    token_hash: Mapped[str] = mapped_column(String(255))
    expire_at: Mapped[datetime] = mapped_column(DateTime)
    revoked: Mapped[bool] = mapped_column(Boolean, default=False)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=text("now()"))

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="refresh_token")
    organization: Mapped["Organization"] = relationship("Organization", back_populates="refresh_tokens")
