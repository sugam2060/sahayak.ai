from datetime import datetime
from uuid import UUID, uuid4
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, DateTime, ForeignKey, text, Text
from shared.database.schema.base import Base

class Team(Base):
    __tablename__ = "teams"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4, server_default=text("gen_random_uuid()"))
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"))
    
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=text("now()"))

    # Relationships
    organization: Mapped["Organization"] = relationship("Organization", back_populates="teams")
    members: Mapped[list["TeamMember"]] = relationship("TeamMember", back_populates="team", cascade="all, delete-orphan")

class TeamMember(Base):
    __tablename__ = "team_members"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4, server_default=text("gen_random_uuid()"))
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    team_id: Mapped[UUID] = mapped_column(ForeignKey("teams.id", ondelete="CASCADE"))
    role: Mapped[str] = mapped_column(String(50), default="member")

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="team_memberships")
    team: Mapped["Team"] = relationship("Team", back_populates="members")
