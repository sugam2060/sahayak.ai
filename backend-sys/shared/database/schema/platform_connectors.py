import enum
from datetime import datetime
from uuid import UUID, uuid4
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, Boolean, DateTime, ForeignKey, text, Enum
from shared.database.schema.base import Base

class PlatformType(enum.Enum):
    INSTAGRAM = "instagram"
    TIKTOK = "tiktok"
    FACEBOOK_MESSENGER = "facebook_messenger"
    CHATBOX = "chatbox"

class PlatformConnector(Base):
    __tablename__ = "platform_connectors"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4, server_default=text("gen_random_uuid()"))
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"))
    
    platform: Mapped[PlatformType] = mapped_column(Enum(PlatformType))
    external_page_id: Mapped[str] = mapped_column(String(255))
    
    access_token: Mapped[str] = mapped_column(String(1024))
    refresh_token: Mapped[str] = mapped_column(String(1024), nullable=True)
    token_expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    webhook_secret: Mapped[str] = mapped_column(String(255), nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=text("now()"), onupdate=text("now()"))

    # Relationships
    organization: Mapped["Organization"] = relationship("Organization", back_populates="connectors")
