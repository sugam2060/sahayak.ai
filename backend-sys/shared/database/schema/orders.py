import enum
from datetime import datetime
from uuid import UUID, uuid4
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, DateTime, ForeignKey, text, Text, Integer, Enum, Index
from sqlalchemy.dialects.postgresql import JSONB
from shared.database.schema.base import Base
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from shared.database.schema.organizations import Organization
    from shared.database.schema.users import User
    from shared.database.schema.products import Product
    from shared.database.schema.customers import Customer

class PlatformType(enum.Enum):
    INSTAGRAM = "instagram"
    TIKTOK = "tiktok"
    FACEBOOK_MESSENGER = "facebook_messenger"
    CHATBOX = "chatbox"
    TELEGRAM = "telegram"

class OrderStatus(enum.Enum):
    PENDING = "pending"
    DISPATCH = "dispatch"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"

class Order(Base):
    __tablename__ = "orders"

    __table_args__ = (
        Index("idx_orders_organization_id", "organization_id"),
        Index("idx_orders_assigned_agent_id", "assigned_agent_id"),
        Index("idx_orders_org_created", "organization_id", "created_at"),
        Index("idx_orders_org_status", "organization_id", "status"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4, server_default=text("gen_random_uuid()"))
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"))
    
    platform: Mapped[PlatformType] = mapped_column(Enum(PlatformType))
    external_customer_id: Mapped[str] = mapped_column(String(255), nullable=True)
    customer_phone: Mapped[str] = mapped_column(String(10), nullable=True)
    delivery_address: Mapped[str] = mapped_column(Text, nullable=True)
    
    status: Mapped[OrderStatus] = mapped_column(Enum(OrderStatus), default=OrderStatus.PENDING)
    total_amount: Mapped[int] = mapped_column(Integer)
    currency: Mapped[str] = mapped_column(String(10), default="NPR")
    tax_amount: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    delivery_charge: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    
    assigned_agent_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    customer_id: Mapped[UUID] = mapped_column(ForeignKey("customers.id", ondelete="SET NULL"), nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=text("now()"), onupdate=text("now()"))

    # Relationships
    organization: Mapped["Organization"] = relationship("Organization", back_populates="orders")
    assigned_agent: Mapped["User"] = relationship("User", back_populates="assigned_orders")
    customer: Mapped["Customer"] = relationship("Customer", back_populates="orders")
    items: Mapped[list["OrderItem"]] = relationship("OrderItem", back_populates="order", cascade="all, delete-orphan")

class OrderItem(Base):
    __tablename__ = "order_items"

    __table_args__ = (
        Index("idx_order_items_order_id", "order_id"),
        Index("idx_order_items_product_id", "product_id"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4, server_default=text("gen_random_uuid()"))
    order_id: Mapped[UUID] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"))
    product_id: Mapped[UUID] = mapped_column(ForeignKey("products.id", ondelete="SET NULL"), nullable=True)
    
    quantity: Mapped[int] = mapped_column(Integer, default=1)
    unit_price: Mapped[int] = mapped_column(Integer)
    snapshot: Mapped[dict] = mapped_column(JSONB, nullable=True)

    # Relationships
    order: Mapped["Order"] = relationship("Order", back_populates="items")
    product: Mapped["Product"] = relationship("Product", back_populates="order_items")
