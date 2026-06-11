from fastapi import APIRouter, Depends, HTTPException, status, File, UploadFile, Form, Request
from uuid import UUID
from typing import Optional

from shared.proto import service_pb2
from services.api_gateway.routers.teams.permissions import check_permission

router = APIRouter(prefix="/api/products")

@router.put("/{product_id}")
async def update_product(
    product_id: UUID,
    request: Request,
    name: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    price: Optional[int] = Form(None),
    currency: Optional[str] = Form(None),
    stock: Optional[int] = Form(None),
    sku: Optional[str] = Form(None),
    is_active: Optional[bool] = Form(None),
    clear_image: Optional[bool] = Form(False),
    metadata_json: Optional[str] = Form(None),
    image_file: Optional[UploadFile] = File(None),
    current_user: dict = Depends(check_permission("products"))
):
    try:
        image_bytes = b""
        image_name = ""
        image_content_type = ""
        
        if image_file:
            if not image_file.content_type.startswith("image/"):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Only image files are allowed."
                )
            image_bytes = await image_file.read()
            image_name = image_file.filename or ""
            image_content_type = image_file.content_type or ""

        grpc_req = service_pb2.UpdateProductRequest(
            organization_id=current_user["organization_id"],
            organization_name=current_user["organization_name"],
            product_id=str(product_id),
            has_name=(name is not None),
            name=name if name is not None else "",
            has_description=(description is not None),
            description=description if description is not None else "",
            has_price=(price is not None),
            price=price if price is not None else 0,
            has_currency=(currency is not None),
            currency=currency if currency is not None else "",
            has_stock=(stock is not None),
            stock=stock if stock is not None else 0,
            has_sku=(sku is not None),
            sku=sku if sku is not None else "",
            has_is_active=(is_active is not None),
            is_active=is_active if is_active is not None else False,
            clear_image=clear_image,
            image_file_bytes=image_bytes,
            image_file_name=image_name,
            image_file_content_type=image_content_type,
            has_metadata_json=(metadata_json is not None),
            metadata_json=metadata_json if metadata_json is not None else ""
        )

        res = await request.app.state.product_stub.UpdateProduct(grpc_req)

        if not res.success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=res.message or "Failed to update product."
            )

        import json
        meta_dict = None
        if res.product.metadata_json:
            try:
                meta_dict = json.loads(res.product.metadata_json)
            except Exception:
                pass

        product_dict = {
            "id": res.product.id,
            "organization_id": res.product.organization_id,
            "name": res.product.name,
            "description": res.product.description if res.product.description else None,
            "price": res.product.price,
            "currency": res.product.currency,
            "stock": res.product.stock,
            "sku": res.product.sku if res.product.sku else None,
            "image": res.product.image if res.product.image else None,
            "is_active": res.product.is_active,
            "created_at": res.product.created_at,
            "updated_at": res.product.updated_at,
            "metadata": meta_dict,
            "share_url": res.product.share_url if res.product.share_url else None
        }

        return {"success": True, "product": product_dict}

    except HTTPException as he:
        raise he
    except Exception as e:
        print(f"Error updating product via gRPC: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update product. Please check your inputs or try again later."
        )

