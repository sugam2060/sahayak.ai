from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from typing import Optional
from uuid import UUID

from shared.proto import service_pb2
from services.api_gateway.routers.teams.permissions import check_permission

router = APIRouter(prefix="/api/products")

def proto_to_product_dict(p):
    import json
    meta_dict = None
    if p.metadata_json:
        try:
            meta_dict = json.loads(p.metadata_json)
        except Exception:
            pass

    return {
        "id": p.id,
        "organization_id": p.organization_id,
        "name": p.name,
        "description": p.description if p.description else None,
        "price": p.price,
        "currency": p.currency,
        "stock": p.stock,
        "sku": p.sku if p.sku else None,
        "image": p.image if p.image else None,
        "is_active": p.is_active,
        "created_at": p.created_at,
        "updated_at": p.updated_at,
        "metadata": meta_dict
    }

@router.get("")
async def get_products(
    request: Request,
    limit: int = Query(default=10, ge=1, le=100),
    cursor: Optional[str] = Query(None, description="Format: {created_at_iso}_{uuid}"),
    search: Optional[str] = Query(None),
    sku: Optional[str] = Query(None),
    is_active: Optional[bool] = Query(None),
    stock_status: Optional[str] = Query(None, description="in_stock or out_of_stock"),
    current_user: dict = Depends(check_permission("products"))
):
    try:
        grpc_req = service_pb2.GetProductsRequest(
            organization_id=current_user["organization_id"],
            limit=limit,
            cursor=cursor or "",
            search=search or "",
            sku=sku or "",
            has_is_active=(is_active is not None),
            is_active=is_active if is_active is not None else False,
            stock_status=stock_status or ""
        )

        res = await request.app.state.product_stub.GetProducts(grpc_req)

        if not res.success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to retrieve products catalog."
            )

        products_list = [proto_to_product_dict(p) for p in res.products]

        return {
            "success": True,
            "products": products_list,
            "next_cursor": res.next_cursor if res.next_cursor else None,
            "has_next": res.has_next
        }
    except HTTPException as he:
        raise he
    except Exception as e:
        print(f"Error retrieving products via gRPC: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve products. Please try again later."
        )

@router.get("/{product_id}")
async def get_product_detail(
    product_id: UUID,
    request: Request,
    current_user: dict = Depends(check_permission("products"))
):
    try:
        grpc_req = service_pb2.GetProductDetailRequest(
            organization_id=current_user["organization_id"],
            product_id=str(product_id)
        )
        res = await request.app.state.product_stub.GetProductDetail(grpc_req)
        
        if not res.success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Product not found."
            )

        return {"success": True, "product": proto_to_product_dict(res.product)}
    except HTTPException as he:
        raise he
    except Exception as e:
        print(f"Error fetching product details via gRPC: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve product details."
        )

