import enum
from datetime import datetime
from uuid import UUID, uuid4
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, DateTime, ForeignKey, text, Text, Integer, Enum
from sqlalchemy.dialects.postgresql import JSONB
from shared.database.schema.base import Base

class PlatformType(enum.Enum):
    INSTAGRAM = "instagram"
    TIKTOK = "tiktok"
    FACEBOOK_MESSENGER = "facebook_messenger"
    CHATBOX = "chatbox"

class OrderStatus(enum.Enum):
    PENDING = "pending"
    DISPATCH = "dispatch"
    DELIVERED = "delivered"

class Order(Base):
    __tablename__ = "orders"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4, server_default=text("gen_random_uuid()"))
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"))
    
    platform: Mapped[PlatformType] = mapped_column(Enum(PlatformType))
    external_customer_id: Mapped[str] = mapped_column(String(255), nullable=True)
    customer_phone: Mapped[str] = mapped_column(String(10), nullable=True)
    delivery_address: Mapped[str] = mapped_column(Text, nullable=True)
    
    status: Mapped[OrderStatus] = mapped_column(Enum(OrderStatus), default=OrderStatus.PENDING)
    total_amount: Mapped[int] = mapped_column(Integer)
    currency: Mapped[str] = mapped_column(String(10), default="NPR")
    
    assigned_agent_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=text("now()"), onupdate=text("now()"))

    # Relationships
    organization: Mapped["Organization"] = relationship("Organization", back_populates="orders")
    assigned_agent: Mapped["User"] = relationship("User", back_populates="assigned_orders")
    items: Mapped[list["OrderItem"]] = relationship("OrderItem", back_populates="order", cascade="all, delete-orphan")

class OrderItem(Base):
    __tablename__ = "order_items"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4, server_default=text("gen_random_uuid()"))
    order_id: Mapped[UUID] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"))
    product_id: Mapped[UUID] = mapped_column(ForeignKey("products.id", ondelete="SET NULL"), nullable=True)
    
    quantity: Mapped[int] = mapped_column(Integer, default=1)
    unit_price: Mapped[int] = mapped_column(Integer)
    snapshot: Mapped[dict] = mapped_column(JSONB, nullable=True)

    # Relationships
    order: Mapped["Order"] = relationship("Order", back_populates="items")
    product: Mapped["Product"] = relationship("Product", back_populates="order_items")
