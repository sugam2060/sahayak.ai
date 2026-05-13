import enum
from datetime import datetime
from uuid import UUID, uuid4
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, Boolean, Enum, DateTime, ForeignKey, text, Index
from shared.database.schema.base import Base

class UserRole(enum.Enum):
    OWNER = "OWNER"
    ADMIN = "ADMIN"
    AGENT = "AGENT"

class User(Base):
    __tablename__ = "users"

    __table_args__ = (
        Index(
            "ix_unique_owner_per_org",
            "organization_id",
            unique=True,
            postgresql_where=text("role = 'OWNER'")
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4, server_default=text("gen_random_uuid()"))
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"))
    
    # Verification
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    full_name: Mapped[str] = mapped_column(String(255))
    
    role: Mapped[UserRole] = mapped_column(Enum(UserRole), default=UserRole.AGENT)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    
    last_login_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    
    # Account Locking
    failed_login_attempts: Mapped[int] = mapped_column(default=0, server_default=text("0"))
    locked_until: Mapped[datetime] = mapped_column(DateTime, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=text("now()"), onupdate=text("now()"))

    # Relationships
    organization: Mapped["Organization"] = relationship("Organization", back_populates="users", foreign_keys=[organization_id])
    refresh_token: Mapped["RefreshToken"] = relationship("RefreshToken", back_populates="user", uselist=False, cascade="all, delete-orphan")
    team_memberships: Mapped[list["TeamMember"]] = relationship("TeamMember", back_populates="user", cascade="all, delete-orphan")
    assigned_orders: Mapped[list["Order"]] = relationship("Order", back_populates="assigned_agent")
