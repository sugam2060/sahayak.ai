import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from uuid import uuid4, UUID
import grpc

from services.workers.orders.handlers import OrderService
from shared.proto import service_pb2
from shared.database.schema.orders import PlatformType

def make_mock_result(scalars_all=None, scalar_first=None, scalar_one_or_none=None):
    mock_res = MagicMock()
    mock_res.scalars.return_value.all.return_value = scalars_all
    mock_res.scalars.return_value.first.return_value = scalar_first
    mock_res.scalar_one_or_none.return_value = scalar_one_or_none
    return mock_res

@pytest.mark.asyncio
async def test_create_order_invalid_uuid_product_ids():
    service = OrderService()
    # Create request with invalid product id (bad UUID)
    request = service_pb2.CreateOrderRequest(
        organization_id=str(uuid4()),
        agent_id=str(uuid4()),
        platform="instagram",
        external_customer_id="customer-123",
        customer_phone="9876543210",
        delivery_address="Kathmandu",
        items=[
            service_pb2.OrderItemCreateInput(product_id="prod_invalid_uuid", quantity=1)
        ]
    )
    
    mock_context = MagicMock()
    response = await service.CreateOrder(request, mock_context)
    
    assert response.success is False
    assert "Invalid product ID format" in response.message
    mock_context.set_code.assert_called_once_with(grpc.StatusCode.INVALID_ARGUMENT)


@pytest.mark.asyncio
async def test_create_order_missing_customer_info():
    service = OrderService()
    # Request without phone or delivery address
    org_id = uuid4()
    request = service_pb2.CreateOrderRequest(
        organization_id=str(org_id),
        agent_id="",  # empty so we bypass agent DB query
        platform="instagram",
        external_customer_id="customer-123",
        items=[
            service_pb2.OrderItemCreateInput(product_id=str(uuid4()), quantity=1)
        ]
    )
    
    mock_product = MagicMock()
    mock_product.id = UUID(request.items[0].product_id)
    mock_product.stock = 10
    mock_product.price = 100
    mock_product.name = "Logitech G77"
    mock_product.sku = "LOGI-77"
    mock_product.currency = "NPR"
    mock_product.description = "Headset"
    mock_product.image = ""

    mock_db = MagicMock()
    mock_db_session = AsyncMock()
    mock_db.__aenter__.return_value = mock_db_session

    # First query: Products select
    # Second query: Customer select
    mock_product_result = make_mock_result(scalars_all=[mock_product])
    mock_customer_result = make_mock_result(scalar_first=None)
    
    mock_db_session.execute.side_effect = [mock_product_result, mock_customer_result]
    
    mock_context = MagicMock()
    
    with patch("services.workers.orders.handlers.SessionLocal", return_value=mock_db):
        response = await service.CreateOrder(request, mock_context)
        
        assert response.success is False
        assert "Missing customer info" in response.message
        mock_context.set_code.assert_called_with(grpc.StatusCode.INVALID_ARGUMENT)


@pytest.mark.asyncio
async def test_create_order_with_customer_db_fallback():
    service = OrderService()
    org_id = uuid4()
    prod_id = uuid4()
    
    # Request lacks phone and address
    request = service_pb2.CreateOrderRequest(
        organization_id=str(org_id),
        agent_id="",
        platform="instagram",
        external_customer_id="customer-123",
        items=[
            service_pb2.OrderItemCreateInput(product_id=str(prod_id), quantity=1)
        ]
    )
    
    # Mock Customer
    mock_customer = MagicMock()
    mock_customer.id = uuid4()
    mock_customer.phone = "9876543210"
    mock_customer.delivery_address = "Kathmandu Valley"
    mock_customer.name = "Instagram Customer"
    
    # Mock Product
    mock_product = MagicMock()
    mock_product.id = prod_id
    mock_product.stock = 10
    mock_product.price = 100
    mock_product.name = "Logitech G77"
    mock_product.sku = "LOGI-77"
    mock_product.currency = "NPR"
    mock_product.description = "Headset"
    mock_product.image = ""
    
    mock_db = MagicMock()
    mock_db_session = AsyncMock()
    mock_db_session.add = MagicMock()
    mock_db.__aenter__.return_value = mock_db_session
    
    # Execute calls sequence:
    # 1. Product select
    # 2. Customer select
    mock_product_result = make_mock_result(scalars_all=[mock_product])
    mock_customer_result = make_mock_result(scalar_first=mock_customer)
    
    mock_db_session.execute.side_effect = [mock_product_result, mock_customer_result]
    mock_context = MagicMock()
    
    with patch("services.workers.orders.handlers.SessionLocal", return_value=mock_db), \
         patch("shared.utils.encrypt_token", return_value="mock_token"):
         
        response = await service.CreateOrder(request, mock_context)
        
        assert response.success is True
        assert response.tracking_token == "mock_token"
        
        # Verify db.commit was called
        mock_db_session.commit.assert_called_once()
