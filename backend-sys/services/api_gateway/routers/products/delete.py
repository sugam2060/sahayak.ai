from fastapi import APIRouter, Depends, HTTPException, status, Request
from uuid import UUID

from shared.proto import service_pb2
from services.api_gateway.routers.auth_routers.me import get_current_user

router = APIRouter(prefix="/api/products")

@router.delete("/{product_id}")
async def delete_product(
    product_id: UUID,
    request: Request,
    current_user: dict = Depends(get_current_user)
):
    try:
        grpc_req = service_pb2.DeleteProductRequest(
            organization_id=current_user["organization_id"],
            product_id=str(product_id)
        )
        res = await request.app.state.product_stub.DeleteProduct(grpc_req)

        if not res.success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=res.message or "Product not found."
            )

        return {"success": True, "message": "Product successfully deleted."}
    except HTTPException as he:
        raise he
    except Exception as e:
        print(f"Error deleting product via gRPC: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete product. Please try again later."
        )

