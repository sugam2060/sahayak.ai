import grpc
import logging
import asyncio
import re
import hashlib
from uuid import UUID
from datetime import datetime
from sqlalchemy import select, and_, or_

import cloudinary
import cloudinary.uploader

from shared.proto import service_pb2, service_pb2_grpc
from shared.database.engine import SessionLocal
from shared.database.schema.products import Product
from shared.database.mongodb import MongoDBManager
from shared.config import CLOUDINARY_CLOUD_NAME, CLOUDINARY_API_KEY, CLOUDINARY_API_SECRET

logger = logging.getLogger("workers.products")

# Configure Cloudinary
cloudinary.config(
    cloud_name=CLOUDINARY_CLOUD_NAME,
    api_key=CLOUDINARY_API_KEY,
    api_secret=CLOUDINARY_API_SECRET,
    secure=True
)

def to_product_info(product: Product) -> service_pb2.ProductInfo:
    return service_pb2.ProductInfo(
        id=str(product.id),
        organization_id=str(product.organization_id),
        name=product.name,
        description=product.description or "",
        price=product.price,
        currency=product.currency or "NPR",
        stock=product.stock,
        sku=product.sku or "",
        image=product.image or "",
        is_active=product.is_active,
        created_at=product.created_at.isoformat() if product.created_at else "",
        updated_at=product.updated_at.isoformat() if product.updated_at else ""
    )

from shared.utils import upload_cloudinary_image_bytes, delete_cloudinary_image_task


class ProductService(service_pb2_grpc.ProductServiceServicer):
    async def CreateProduct(self, request, context):
        try:
            org_id = UUID(request.organization_id)
            image_url = None
            if request.image_file_bytes:
                if not request.image_file_content_type.startswith("image/"):
                    context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
                    context.set_details("Only image files are allowed.")
                    return service_pb2.CreateProductResponse(success=False, message="Only image files are allowed.")
                
                image_url = await upload_cloudinary_image_bytes(
                    request.image_file_bytes,
                    request.image_file_name,
                    request.image_file_content_type,
                    request.organization_id,
                    request.organization_name
                )

            async with SessionLocal() as db:
                new_product = Product(
                    organization_id=org_id,
                    name=request.name,
                    description=request.description if request.description else None,
                    price=request.price,
                    currency=request.currency if request.currency else "NPR",
                    stock=request.stock,
                    sku=request.sku if request.sku else None,
                    image=image_url,
                    is_active=request.is_active
                )
                db.add(new_product)
                await db.commit()
                await db.refresh(new_product)
                return service_pb2.CreateProductResponse(
                    success=True,
                    product=to_product_info(new_product)
                )
        except Exception as e:
            logger.error(f"Error creating product: {e}")
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(str(e))
            return service_pb2.CreateProductResponse(success=False, message=str(e))

    async def GetProducts(self, request, context):
        try:
            org_id = UUID(request.organization_id)
            filters = [Product.organization_id == org_id]

            if request.search:
                filters.append(
                    or_(
                        Product.name.ilike(f"%{request.search}%"),
                        Product.description.ilike(f"%{request.search}%"),
                        Product.sku.ilike(f"%{request.search}%")
                    )
                )
            if request.sku:
                filters.append(Product.sku == request.sku)
            if request.has_is_active:
                filters.append(Product.is_active == request.is_active)
            if request.stock_status == "in_stock":
                filters.append(Product.stock > 0)
            elif request.stock_status == "out_of_stock":
                filters.append(Product.stock <= 0)

            if request.cursor:
                cursor_time_str, cursor_uuid_str = request.cursor.split("_", 1)
                cursor_time = datetime.fromisoformat(cursor_time_str)
                cursor_uuid = UUID(cursor_uuid_str)
                filters.append(
                    or_(
                        Product.created_at < cursor_time,
                        and_(
                            Product.created_at == cursor_time,
                            Product.id < cursor_uuid
                        )
                    )
                )

            async with SessionLocal() as db:
                stmt = (
                    select(Product)
                    .where(and_(*filters))
                    .order_by(Product.created_at.desc(), Product.id.desc())
                    .limit(request.limit + 1)
                )
                res = await db.execute(stmt)
                products = res.scalars().all()

                has_next = len(products) > request.limit
                next_products = list(products[:request.limit])

                next_cursor = ""
                if has_next and next_products:
                    last_item = next_products[-1]
                    last_time_iso = last_item.created_at.isoformat()
                    next_cursor = f"{last_time_iso}_{str(last_item.id)}"

                return service_pb2.GetProductsResponse(
                    success=True,
                    products=[to_product_info(p) for p in next_products],
                    next_cursor=next_cursor,
                    has_next=has_next
                )
        except Exception as e:
            logger.error(f"Error getting products: {e}")
            context.set_code(grpc.StatusCode.INTERNAL)
            return service_pb2.GetProductsResponse(success=False)

    async def GetProductDetail(self, request, context):
        try:
            org_id = UUID(request.organization_id)
            prod_id = UUID(request.product_id)
            async with SessionLocal() as db:
                stmt = select(Product).where(Product.id == prod_id, Product.organization_id == org_id)
                res = await db.execute(stmt)
                product = res.scalar_one_or_none()
                if not product:
                    context.set_code(grpc.StatusCode.NOT_FOUND)
                    return service_pb2.GetProductDetailResponse(success=False)
                return service_pb2.GetProductDetailResponse(success=True, product=to_product_info(product))
        except Exception as e:
            logger.error(f"Error getting product detail: {e}")
            context.set_code(grpc.StatusCode.INTERNAL)
            return service_pb2.GetProductDetailResponse(success=False)

    async def UpdateProduct(self, request, context):
        try:
            org_id = UUID(request.organization_id)
            prod_id = UUID(request.product_id)
            async with SessionLocal() as db:
                stmt = select(Product).where(Product.id == prod_id, Product.organization_id == org_id)
                res = await db.execute(stmt)
                product = res.scalar_one_or_none()
                if not product:
                    context.set_code(grpc.StatusCode.NOT_FOUND)
                    return service_pb2.UpdateProductResponse(success=False, message="Product not found.")

                old_image = product.image
                new_image = None
                should_delete_old = False

                if request.image_file_bytes:
                    if not request.image_file_content_type.startswith("image/"):
                        context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
                        return service_pb2.UpdateProductResponse(success=False, message="Only image files are allowed.")
                    new_image = await upload_cloudinary_image_bytes(
                        request.image_file_bytes,
                        request.image_file_name,
                        request.image_file_content_type,
                        request.organization_id,
                        request.organization_name
                    )
                    product.image = new_image
                    if old_image:
                        should_delete_old = True
                elif request.clear_image:
                    product.image = None
                    if old_image:
                        should_delete_old = True

                if request.has_name:
                    product.name = request.name
                if request.has_description:
                    product.description = request.description if request.description != "" else None
                if request.has_price:
                    product.price = request.price
                if request.has_currency:
                    product.currency = request.currency
                if request.has_stock:
                    product.stock = request.stock
                if request.has_sku:
                    product.sku = request.sku if request.sku != "" else None
                if request.has_is_active:
                    product.is_active = request.is_active

                await db.commit()

                if should_delete_old and old_image:
                    asyncio.create_task(delete_cloudinary_image_task(old_image))

                await db.refresh(product)
                return service_pb2.UpdateProductResponse(success=True, product=to_product_info(product))
        except Exception as e:
            logger.error(f"Error updating product: {e}")
            context.set_code(grpc.StatusCode.INTERNAL)
            return service_pb2.UpdateProductResponse(success=False, message=str(e))

    async def DeleteProduct(self, request, context):
        try:
            org_id = UUID(request.organization_id)
            prod_id = UUID(request.product_id)
            async with SessionLocal() as db:
                stmt = select(Product).where(Product.id == prod_id, Product.organization_id == org_id)
                res = await db.execute(stmt)
                product = res.scalar_one_or_none()
                if not product:
                    context.set_code(grpc.StatusCode.NOT_FOUND)
                    return service_pb2.DeleteProductResponse(success=False, message="Product not found.")

                old_image = product.image
                await db.delete(product)
                await db.commit()

                if old_image:
                    asyncio.create_task(delete_cloudinary_image_task(old_image))

                return service_pb2.DeleteProductResponse(success=True, message="Product successfully deleted.")
        except Exception as e:
            logger.error(f"Error deleting product: {e}")
            context.set_code(grpc.StatusCode.INTERNAL)
            return service_pb2.DeleteProductResponse(success=False, message=str(e))
