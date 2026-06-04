"""
Tool: Get detailed product information via gRPC.
"""
import logging
from typing import Annotated
from langchain_core.tools import tool
from langgraph.prebuilt import InjectedState
from shared.proto import service_pb2
from ...grpc_client import WorkersGRPCClient

logger = logging.getLogger("chatai_service.ai.tools.products.get_product_detail")


@tool
async def get_product_detail(
    organization_id: Annotated[str, InjectedState("organization_id")],
    product_id: str
) -> str:
    """Get detailed information about a specific product.
    
    Args:
        organization_id: The organization's UUID (injected from state).
        product_id: The UUID of the product.
    """
    try:
        _, product_stub, _ = WorkersGRPCClient.get_stubs()
        
        request = service_pb2.GetProductDetailRequest(
            organization_id=organization_id,
            product_id=product_id
        )
        
        response = await product_stub.GetProductDetail(request)
        
        if response.success and response.product:
            p = response.product
            stock_status = f"In Stock ({p.stock} available)" if p.stock > 0 else "Out of Stock"
            return (
                f"Product Details:\n"
                f"Name: {p.name}\n"
                f"ID: {p.id}\n"
                f"Price: {p.price} {p.currency}\n"
                f"Stock: {stock_status}\n"
                f"SKU: {p.sku or 'N/A'}\n"
                f"Description: {p.description or 'No description'}\n"
                f"Image: {p.image or 'No image'}\n"
                f"Active: {p.is_active}"
            )
        else:
            return f"Product not found with ID: {product_id}"
    except Exception as e:
        logger.error(f"Error getting product detail: {e}", exc_info=True)
        return f"Error getting product details: {str(e)}"
