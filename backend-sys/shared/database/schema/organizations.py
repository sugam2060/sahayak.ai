import enum
from datetime import datetime
from uuid import UUID, uuid4
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, Boolean, Enum, DateTime, text, ForeignKey
from shared.database.schema.base import Base
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from shared.database.schema.users import User
    from shared.database.schema.organization_config_ai import OrganizationConfigAI
    from shared.database.schema.refresh_tokens import RefreshToken
    from shared.database.schema.teams import Team
    from shared.database.schema.products import Product
    from shared.database.schema.orders import Order
    from shared.database.schema.platform_connectors import PlatformConnector

class PlanType(enum.Enum):
    FREE = "free"
    PREMIUM = "premium"

class Organization(Base):
    __tablename__ = "organizations"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4, server_default=text("gen_random_uuid()"))
    name: Mapped[str] = mapped_column(String(255))
    slug: Mapped[str] = mapped_column(String(100), unique=True)
    plan: Mapped[PlanType] = mapped_column(Enum(PlanType), default=PlanType.FREE)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    owner_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE", use_alter=True, name="fk_org_owner_id"), nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=text("now()"), onupdate=text("now()"))

    # Relationships
    owner: Mapped["User"] = relationship("User", foreign_keys=[owner_id], post_update=True)
    users: Mapped[list["User"]] = relationship("User", back_populates="organization", foreign_keys="User.organization_id", cascade="all, delete-orphan")
    ai_config: Mapped["OrganizationConfigAI"] = relationship("OrganizationConfigAI", back_populates="organization", uselist=False, cascade="all, delete-orphan")
    refresh_tokens: Mapped[list["RefreshToken"]] = relationship("RefreshToken", back_populates="organization", cascade="all, delete-orphan")
    teams: Mapped[list["Team"]] = relationship("Team", back_populates="organization", cascade="all, delete-orphan")
    products: Mapped[list["Product"]] = relationship("Product", back_populates="organization", cascade="all, delete-orphan")
    orders: Mapped[list["Order"]] = relationship("Order", back_populates="organization", cascade="all, delete-orphan")
    # Connectors relationship: holds multiple connectors for different platforms.
    # An organization can have multiple platform connectors, but is limited to at most one per platform type
    # by the unique constraint `uq_org_platform_connector` in the `platform_connectors` table.
    connectors: Mapped[list["PlatformConnector"]] = relationship("PlatformConnector", back_populates="organization", cascade="all, delete-orphan")
