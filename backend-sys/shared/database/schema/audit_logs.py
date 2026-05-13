import enum
from datetime import datetime
from uuid import UUID, uuid4
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, Enum, DateTime, ForeignKey, text, JSON
from shared.database.schema.base import Base

class AuditEventType(enum.Enum):
    LOGIN_SUCCESS = "LOGIN_SUCCESS"
    LOGIN_FAILED = "LOGIN_FAILED"
    ACCOUNT_LOCKED = "ACCOUNT_LOCKED"
    TOKEN_REFRESH = "TOKEN_REFRESH"
    PASSWORD_CHANGE = "PASSWORD_CHANGE"
    EMAIL_VERIFICATION = "EMAIL_VERIFICATION"

class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4, server_default=text("gen_random_uuid()"))
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="SET NULL"), nullable=True)
    
    event_type: Mapped[AuditEventType] = mapped_column(Enum(AuditEventType))
    ip_address: Mapped[str] = mapped_column(String(45), nullable=True)  # Supports IPv6
    user_agent: Mapped[str] = mapped_column(String(512), nullable=True)
    
    details: Mapped[dict] = mapped_column(JSON, nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=text("now()"))
