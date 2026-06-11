from fastapi import APIRouter, Depends, HTTPException, status, File, UploadFile, Form, Request
from uuid import UUID
from typing import Optional

from shared.proto import service_pb2
from services.api_gateway.routers.teams.permissions import check_permission

router = APIRouter(prefix="/api/products")

@router.post("", status_code=status.HTTP_201_CREATED)
async def create_product(
    request: Request,
    name: str = Form(...),
    description: Optional[str] = Form(None),
    price: int = Form(...),
    currency: str = Form("NPR"),
    stock: int = Form(0),
    sku: Optional[str] = Form(None),
    is_active: bool = Form(True),
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

        grpc_req = service_pb2.CreateProductRequest(
            organization_id=current_user["organization_id"],
            organization_name=current_user["organization_name"],
            name=name,
            description=description or "",
            price=price,
            currency=currency,
            stock=stock,
            sku=sku or "",
            is_active=is_active,
            image_file_bytes=image_bytes,
            image_file_name=image_name,
            image_file_content_type=image_content_type,
            metadata_json=metadata_json or ""
        )

        res = await request.app.state.product_stub.CreateProduct(grpc_req)
        
        if not res.success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=res.message or "Failed to create product."
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
            "description": res.product.description,
            "price": res.product.price,
            "currency": res.product.currency,
            "stock": res.product.stock,
            "sku": res.product.sku,
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
        print(f"Error creating product via gRPC: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create product. Please check your inputs or try again later."
        )

