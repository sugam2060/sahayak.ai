"""
Tool: Search products via gRPC.
"""
import logging
from typing import Annotated
from langchain_core.tools import tool
from langgraph.prebuilt import InjectedState
from shared.proto import service_pb2
from ...grpc_client import WorkersGRPCClient

logger = logging.getLogger("chatai_service.ai.tools.products.search_products")


@tool
async def search_products(
    organization_id: Annotated[str, InjectedState("organization_id")],
    query: str = "",
    limit: int = 10
) -> str:
    """Search for products in the catalog. Use when a customer asks about available products.
    
    Args:
        organization_id: The organization's UUID (injected from state).
        query: Search term to filter products by name, description, or SKU. Leave empty to list all.
        limit: Maximum number of products to return (default 10).
    """
    try:
        _, product_stub, _ = WorkersGRPCClient.get_stubs()
        
        request = service_pb2.GetProductsRequest(
            organization_id=organization_id,
            limit=limit,
            search=query,
            has_is_active=True,
            is_active=True  # Only show active products to customers
        )
        
        response = await product_stub.GetProducts(request)
        
        if response.success:
            if not response.products:
                return f"No products found matching '{query}'." if query else "No products available."
            
            product_lines = []
            for p in response.products:
                stock_status = f"In Stock ({p.stock})" if p.stock > 0 else "Out of Stock"
                product_lines.append(
                    f"- {p.name} (ID: {p.id})\n"
                    f"  Price: {p.price} {p.currency} | {stock_status}\n"
                    f"  {p.description[:100] if p.description else 'No description'}"
                )
            
            result = f"Found {len(response.products)} products:\n\n"
            result += "\n\n".join(product_lines)
            return result
        else:
            return "Failed to search products."
    except Exception as e:
        logger.error(f"Error searching products: {e}", exc_info=True)
        return f"Error searching products: {str(e)}"
