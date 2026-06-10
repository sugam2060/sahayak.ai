import pytest
import importlib
from unittest.mock import AsyncMock, patch, MagicMock
from shared.proto import service_pb2

search_products_module = importlib.import_module("services.chatai-service.ai.tools.products.search_products")
search_products = search_products_module.search_products

@pytest.mark.asyncio
async def test_search_products_success():
    # Mock WorkersGRPCClient.get_stubs
    mock_stub = MagicMock()
    
    # Prepare responses
    resp = MagicMock()
    resp.success = True
    p1 = MagicMock()
    p1.id = "p-1"
    p1.name = "RTX 4090"
    p1.price = 1599.0
    p1.currency = "USD"
    p1.stock = 5
    p1.description = "Flagship GPU"
    resp.products = [p1]
    
    mock_stub.GetProducts = AsyncMock(return_value=resp)
    
    with patch.object(search_products_module.WorkersGRPCClient, "get_stubs", return_value=(None, mock_stub, None)):
        result = await search_products.ainvoke({
            "organization_id": "test-org",
            "query": "rtx 4090",
            "limit": 10
        })
        
        assert "RTX 4090" in result
        assert "1599" in result
        mock_stub.GetProducts.assert_called_once()
        args, kwargs = mock_stub.GetProducts.call_args
        request = args[0]
        assert request.organization_id == "test-org"
        assert request.search == "rtx 4090"
        assert request.limit == 10

@pytest.mark.asyncio
async def test_search_products_no_results():
    # Mock WorkersGRPCClient.get_stubs
    mock_stub = MagicMock()
    resp = MagicMock()
    resp.success = True
    resp.products = []
    mock_stub.GetProducts = AsyncMock(return_value=resp)
    
    with patch.object(search_products_module.WorkersGRPCClient, "get_stubs", return_value=(None, mock_stub, None)):
        result = await search_products.ainvoke({
            "organization_id": "test-org",
            "query": "nonexistent",
            "limit": 10
        })
        
        assert "No products found matching 'nonexistent'" in result
