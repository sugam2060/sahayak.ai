from datetime import datetime
from uuid import UUID, uuid4
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, Boolean, DateTime, ForeignKey, text, Text, Integer
from sqlalchemy.dialects.postgresql import JSONB
from shared.database.schema.base import Base

class Product(Base):
    __tablename__ = "products"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4, server_default=text("gen_random_uuid()"))
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"))
    
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text, nullable=True)
    price: Mapped[int] = mapped_column(Integer)
    currency: Mapped[str] = mapped_column(String(10), default="NPR")
    stock: Mapped[int] = mapped_column(Integer, default=0)
    sku: Mapped[str] = mapped_column(String(100), nullable=True)
    image: Mapped[str] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    
    metadata_json: Mapped[dict] = mapped_column(JSONB, nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=text("now()"), onupdate=text("now()"))

    # Relationships
    organization: Mapped["Organization"] = relationship("Organization", back_populates="products")
    order_items: Mapped[list["OrderItem"]] = relationship("OrderItem", back_populates="product")
