import grpc
import json
import logging
from uuid import UUID
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from shared.proto import service_pb2, service_pb2_grpc
from shared.database.engine import SessionLocal
from shared.database.schema.products import Product
from shared.database.schema.orders import Order, OrderItem, PlatformType, OrderStatus

logger = logging.getLogger("workers.orders")

def to_order_info(order: Order) -> service_pb2.OrderInfo:
    items = []
    if order.items:
        for item in order.items:
            items.append(
                service_pb2.OrderItemInfo(
                    id=str(item.id),
                    product_id=str(item.product_id) if item.product_id else "",
                    quantity=item.quantity,
                    unit_price=item.unit_price,
                    snapshot_json=json.dumps(item.snapshot) if item.snapshot else "{}"
                )
            )
    return service_pb2.OrderInfo(
        id=str(order.id),
        organization_id=str(order.organization_id),
        platform=order.platform.value,
        external_customer_id=order.external_customer_id or "",
        customer_phone=order.customer_phone or "",
        delivery_address=order.delivery_address or "",
        status=order.status.value,
        total_amount=order.total_amount,
        currency=order.currency or "NPR",
        assigned_agent_id=str(order.assigned_agent_id) if order.assigned_agent_id else "",
        created_at=order.created_at.isoformat() if order.created_at else "",
        updated_at=order.updated_at.isoformat() if order.updated_at else "",
        items=items,
        tax_amount=order.tax_amount or 0,
        delivery_charge=order.delivery_charge or 0
    )

class OrderService(service_pb2_grpc.OrderServiceServicer):
    async def CreateOrder(self, request, context):
        try:
            org_id = UUID(request.organization_id)
            agent_id = UUID(request.agent_id)

            try:
                platform_enum = PlatformType(request.platform.lower())
            except ValueError:
                context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
                return service_pb2.CreateOrderResponse(success=False, message="Invalid platform.")

            if not request.items:
                context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
                return service_pb2.CreateOrderResponse(success=False, message="Order must contain at least one item.")

            product_ids = [UUID(item.product_id) for item in request.items]
            async with SessionLocal() as db:
                stmt = select(Product).where(Product.id.in_(product_ids), Product.organization_id == org_id)
                res = await db.execute(stmt)
                products = {p.id: p for p in res.scalars().all()}

                for pid in product_ids:
                    if pid not in products:
                        context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
                        return service_pb2.CreateOrderResponse(success=False, message=f"Product {pid} not found or unauthorized.")

                # Verify stock sufficiency
                for item in request.items:
                    prod = products[UUID(item.product_id)]
                    if prod.stock < item.quantity:
                        context.set_code(grpc.StatusCode.FAILED_PRECONDITION)
                        return service_pb2.CreateOrderResponse(
                            success=False,
                            message=f"Insufficient stock for product: {prod.name} (Available: {prod.stock}, Requested: {item.quantity})"
                        )

                order_items = []
                total_amount = 0

                for item in request.items:
                    prod = products[UUID(item.product_id)]
                    # Deduct stock
                    prod.stock -= item.quantity
                    
                    unit_price = prod.price
                    item_total = unit_price * item.quantity
                    total_amount += item_total

                    snapshot = {
                        "name": prod.name,
                        "sku": prod.sku,
                        "price": prod.price,
                        "currency": prod.currency,
                        "description": prod.description,
                        "image": prod.image
                    }

                    order_item = OrderItem(
                        product_id=prod.id,
                        quantity=item.quantity,
                        unit_price=unit_price,
                        snapshot=snapshot
                    )
                    order_items.append(order_item)

                items_subtotal = total_amount
                tax_percentage = request.tax_percentage or 0
                tax_amount = int(round(items_subtotal * (tax_percentage / 100.0)))
                delivery_charge = request.delivery_charge or 0
                total_amount += tax_amount + delivery_charge

                new_order = Order(
                    organization_id=org_id,
                    platform=platform_enum,
                    external_customer_id=request.external_customer_id if request.external_customer_id else None,
                    customer_phone=request.customer_phone if request.customer_phone else None,
                    delivery_address=request.delivery_address if request.delivery_address else None,
                    status=OrderStatus.PENDING,
                    total_amount=total_amount,
                    currency=request.currency if request.currency else "NPR",
                    assigned_agent_id=agent_id,
                    items=order_items,
                    tax_amount=tax_amount,
                    delivery_charge=delivery_charge
                )

                db.add(new_order)
                await db.commit()
                await db.refresh(new_order)

                from shared.utils import encrypt_token
                from shared.config import JWT_SECRET
                token = encrypt_token(str(org_id), str(new_order.id), JWT_SECRET)

                return service_pb2.CreateOrderResponse(
                    success=True,
                    order_id=str(new_order.id),
                    total_amount=new_order.total_amount,
                    status=new_order.status.value,
                    tracking_token=token
                )
        except Exception as e:
            logger.error(f"Error creating order: {e}")
            context.set_code(grpc.StatusCode.INTERNAL)
            return service_pb2.CreateOrderResponse(success=False, message=str(e))

    async def GetOrderDetails(self, request, context):
        try:
            org_id = UUID(request.organization_id)
            order_id = UUID(request.order_id)
            async with SessionLocal() as db:
                stmt = (
                    select(Order)
                    .where(Order.id == order_id, Order.organization_id == org_id)
                    .options(selectinload(Order.items))
                )
                res = await db.execute(stmt)
                order = res.scalar_one_or_none()
                if not order:
                    context.set_code(grpc.StatusCode.NOT_FOUND)
                    return service_pb2.GetOrderDetailsResponse(success=False)
                return service_pb2.GetOrderDetailsResponse(success=True, order=to_order_info(order))
        except Exception as e:
            logger.error(f"Error getting order details: {e}")
            context.set_code(grpc.StatusCode.INTERNAL)
            return service_pb2.GetOrderDetailsResponse(success=False)

    async def ListOrders(self, request, context):
        try:
            org_id = UUID(request.organization_id)
            async with SessionLocal() as db:
                stmt = (
                    select(Order)
                    .where(Order.organization_id == org_id)
                    .order_by(Order.created_at.desc())
                    .options(selectinload(Order.items))
                )
                res = await db.execute(stmt)
                orders = res.scalars().all()
                return service_pb2.ListOrdersResponse(
                    success=True,
                    orders=[to_order_info(o) for o in orders]
                )
        except Exception as e:
            logger.error(f"Error listing orders: {e}")
            context.set_code(grpc.StatusCode.INTERNAL)
            return service_pb2.ListOrdersResponse(success=False)

    async def UpdateOrderStatus(self, request, context):
        try:
            org_id = UUID(request.organization_id)
            order_id = UUID(request.order_id)

            try:
                status_enum = OrderStatus(request.status.lower())
            except ValueError:
                context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
                return service_pb2.UpdateOrderStatusResponse(success=False, message="Invalid order status.")

            async with SessionLocal() as db:
                stmt = (
                    select(Order)
                    .where(Order.id == order_id, Order.organization_id == org_id)
                    .options(selectinload(Order.items))
                )
                res = await db.execute(stmt)
                order = res.scalar_one_or_none()
                if not order:
                    context.set_code(grpc.StatusCode.NOT_FOUND)
                    return service_pb2.UpdateOrderStatusResponse(success=False, message="Order not found.")

                # If transitioning to CANCELLED and not already CANCELLED, restore stock
                if status_enum == OrderStatus.CANCELLED and order.status != OrderStatus.CANCELLED:
                    product_ids = [item.product_id for item in order.items if item.product_id]
                    if product_ids:
                        prod_stmt = select(Product).where(Product.id.in_(product_ids), Product.organization_id == org_id)
                        prod_res = await db.execute(prod_stmt)
                        products = {p.id: p for p in prod_res.scalars().all()}
                        
                        for item in order.items:
                            if item.product_id in products:
                                products[item.product_id].stock += item.quantity

                # If transitioning from CANCELLED to an active status, deduct stock after checking sufficiency
                elif order.status == OrderStatus.CANCELLED and status_enum != OrderStatus.CANCELLED:
                    product_ids = [item.product_id for item in order.items if item.product_id]
                    if product_ids:
                        prod_stmt = select(Product).where(Product.id.in_(product_ids), Product.organization_id == org_id)
                        prod_res = await db.execute(prod_stmt)
                        products = {p.id: p for p in prod_res.scalars().all()}
                        
                        # Validate stock sufficiency
                        for item in order.items:
                            if item.product_id not in products:
                                context.set_code(grpc.StatusCode.FAILED_PRECONDITION)
                                return service_pb2.UpdateOrderStatusResponse(
                                    success=False,
                                    message=f"Product {item.product_id} no longer exists or unauthorized."
                                )
                            prod = products[item.product_id]
                            if prod.stock < item.quantity:
                                context.set_code(grpc.StatusCode.FAILED_PRECONDITION)
                                return service_pb2.UpdateOrderStatusResponse(
                                    success=False,
                                    message=f"Insufficient stock to reactivate order. Product: {prod.name} (Available: {prod.stock}, Required: {item.quantity})"
                                )
                        
                        # Deduct stock
                        for item in order.items:
                            products[item.product_id].stock -= item.quantity

                order.status = status_enum
                await db.commit()
                await db.refresh(order)

                return service_pb2.UpdateOrderStatusResponse(
                    success=True,
                    order_id=str(order.id),
                    status=order.status.value
                )
        except Exception as e:
            logger.error(f"Error updating order status: {e}")
            context.set_code(grpc.StatusCode.INTERNAL)
            return service_pb2.UpdateOrderStatusResponse(success=False, message=str(e))
