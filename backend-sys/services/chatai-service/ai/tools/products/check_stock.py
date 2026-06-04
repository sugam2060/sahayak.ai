"""
Tool: Check product stock availability via gRPC.
"""
import logging
from typing import Annotated
from langchain_core.tools import tool
from langgraph.prebuilt import InjectedState
from shared.proto import service_pb2
from ...grpc_client import WorkersGRPCClient

logger = logging.getLogger("chatai_service.ai.tools.products.check_stock")


@tool
async def check_stock(
    organization_id: Annotated[str, InjectedState("organization_id")],
    product_id: str
) -> str:
    """Check the stock availability of a specific product.
    
    Args:
        organization_id: The organization's UUID (injected from state).
        product_id: The UUID of the product to check stock for.
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
            if p.stock > 0:
                return f"{p.name} is in stock. Available quantity: {p.stock}"
            else:
                return f"{p.name} is currently out of stock."
        else:
            return f"Product not found with ID: {product_id}"
    except Exception as e:
        logger.error(f"Error checking stock: {e}", exc_info=True)
        return f"Error checking stock: {str(e)}"
