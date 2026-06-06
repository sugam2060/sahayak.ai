from datetime import datetime
from uuid import UUID, uuid4
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, Boolean, DateTime, ForeignKey, text, Text
from shared.database.schema.base import Base

class OrganizationConfigAI(Base):
    __tablename__ = "organization_config_ai"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4, server_default=text("gen_random_uuid()"))
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), unique=True)
    
    ai_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    auto_order_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    system_prompt: Mapped[str] = mapped_column(String(500), nullable=True)
    knowledge_base: Mapped[str] = mapped_column(Text, nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=text("now()"), onupdate=text("now()"))

    # Relationships
    organization: Mapped["Organization"] = relationship("Organization", back_populates="ai_config")
