from datetime import datetime
from uuid import UUID, uuid4
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, DateTime, ForeignKey, text, UniqueConstraint, Index
from sqlalchemy.dialects.postgresql import JSONB
from shared.database.schema.base import Base

class PlatformConnector(Base):
    __tablename__ = "platform_connectors"

    __table_args__ = (
        UniqueConstraint("business_id", "platform", "platform_account_id", name="unique_business_platform_account"),
        UniqueConstraint("business_id", "platform", name="uq_business_platform"),
        Index("idx_platform_connectors_business_id", "business_id"),
        Index("idx_platform_connectors_routing", "platform", "platform_account_id"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4, server_default=text("gen_random_uuid()"))
    
    # Tenant & Routing Identifiers
    business_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    platform: Mapped[str] = mapped_column(String(50), nullable=False)
    
    # The External Identity
    platform_account_id: Mapped[str] = mapped_column(String(255), nullable=False)
    platform_account_name: Mapped[str] = mapped_column(String(255), nullable=True)
    
    # Credentials & Configuration
    tokens: Mapped[dict] = mapped_column(JSONB, nullable=False)
    platform_metadata: Mapped[dict] = mapped_column("metadata", JSONB, nullable=True, server_default=text("'{}'::jsonb"))
    webhook_secret: Mapped[str] = mapped_column(String(255), nullable=True)
    
    # State Management
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'active'"), default="active")
    
    # Audit Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP"), onupdate=text("CURRENT_TIMESTAMP"))

    # Relationships
    organization: Mapped["Organization"] = relationship("Organization", back_populates="connectors")
