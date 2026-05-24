from uuid import UUID
from sqlalchemy.future import select
from langchain_core.tools import tool
from shared.database.engine import SessionLocal
from shared.database.schema.products import Product

@tool
async def lookup_products(organization_id: str, query: str) -> str:
    """
    Search for active products matching a query (name or description) in the current organization config.
    Returns details including price, currency, stock availability, description, and SKU.
    """
    try:
        org_uuid = UUID(organization_id)
    except ValueError:
        return "Error: Invalid organization ID format."

    try:
        async with SessionLocal() as session:
            stmt = select(Product).where(
                Product.organization_id == org_uuid,
                Product.is_active == True,
                (Product.name.ilike(f"%{query}%") | Product.description.ilike(f"%{query}%"))
            )
            result = await session.execute(stmt)
            products = result.scalars().all()

            if not products:
                return f"No active products found matching '{query}'."

            lines = []
            for p in products:
                desc = p.description or "No description"
                lines.append(f"- Name: {p.name}, Description: {desc}, Price: {p.price} {p.currency}, Stock: {p.stock} units, SKU: {p.sku or 'N/A'}")
            return "\n".join(lines)
    except Exception as e:
        return f"Error executing product lookup: {str(e)}"

@tool
async def check_product_availability(organization_id: str, product_name: str) -> str:
    """
    Check the current stock level and details of a product by name.
    """
    try:
        org_uuid = UUID(organization_id)
    except ValueError:
        return "Error: Invalid organization ID format."

    try:
        async with SessionLocal() as session:
            stmt = select(Product).where(
                Product.organization_id == org_uuid,
                Product.is_active == True,
                Product.name.ilike(f"%{product_name}%")
            )
            result = await session.execute(stmt)
            product = result.scalars().first()

            if not product:
                return f"Product '{product_name}' not found."

            return f"Product: {product.name}, Stock level: {product.stock} units available, Price: {product.price} {product.currency}."
    except Exception as e:
        return f"Error checking product stock level: {str(e)}"
