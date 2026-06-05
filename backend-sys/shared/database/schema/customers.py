from datetime import datetime
from uuid import UUID, uuid4
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, DateTime, ForeignKey, text, Enum, Index
from sqlalchemy.dialects.postgresql import JSONB
from shared.database.schema.base import Base
from shared.database.schema.orders import PlatformType
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from shared.database.schema.organizations import Organization
    from shared.database.schema.orders import Order
    from shared.database.schema.tickets import Ticket

class Customer(Base):
    __tablename__ = "customers"

    __table_args__ = (
        Index("idx_customers_organization_id", "organization_id"),
        Index("idx_customers_org_platform_external", "organization_id", "platform", "external_id", unique=True),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4, server_default=text("gen_random_uuid()"))
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"))
    
    name: Mapped[str] = mapped_column(String(255))
    phone: Mapped[str] = mapped_column(String(10), nullable=True)
    email: Mapped[str] = mapped_column(String(255), nullable=True)
    
    platform: Mapped[PlatformType] = mapped_column(Enum(PlatformType))
    external_id: Mapped[str] = mapped_column(String(255))
    social_media_details: Mapped[dict] = mapped_column(JSONB, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=text("now()"), onupdate=text("now()"))

    # Relationships
    organization: Mapped["Organization"] = relationship("Organization", back_populates="customers")
    orders: Mapped[list["Order"]] = relationship("Order", back_populates="customer", cascade="all, delete-orphan")
    tickets: Mapped[list["Ticket"]] = relationship("Ticket", back_populates="customer", cascade="all, delete-orphan")
