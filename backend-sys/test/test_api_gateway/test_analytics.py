import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import status
from uuid import uuid4, UUID
from datetime import datetime, timedelta
from shared.database.schema import Order, OrderStatus, PlatformType, Ticket, TicketStatus
from shared.utils import get_db


@pytest.fixture
def override_db(test_client, mock_db_session):
    from shared.utils import get_db as route_get_db

    async def _get_db():
        yield mock_db_session

    test_client.app.dependency_overrides[route_get_db] = _get_db
    yield
    test_client.app.dependency_overrides.pop(route_get_db, None)


def _mock_analytics_db(mock_db_session):
    """
    Set up the mock_db_session to return deterministic analytics results
    for all 6 queries inside AnalyticsService.get_overview_metrics.
    """
    org_id = UUID("11111111-2222-3333-4444-555555555555")

    # Build separate mock results for each sequential db.execute call
    # 1. Total revenue
    revenue_result = MagicMock()
    revenue_result.scalar.return_value = 50000

    # 2. Orders by status
    status_result = MagicMock()
    status_result.all.return_value = [
        (OrderStatus.PENDING, 10),
        (OrderStatus.DISPATCH, 5),
        (OrderStatus.DELIVERED, 20),
        (OrderStatus.CANCELLED, 3),
    ]

    # 3. Platform metrics
    platform_result = MagicMock()
    platform_result.all.return_value = [
        (PlatformType.TELEGRAM, 15, 20000),
        (PlatformType.INSTAGRAM, 20, 30000),
    ]

    # 4. Daily sales trend
    trend_result = MagicMock()
    trend_result.all.return_value = [
        ("2026-06-01", 5, 10000),
        ("2026-06-02", 8, 15000),
    ]

    # 5. Tickets by status
    tickets_result = MagicMock()
    tickets_result.all.return_value = [
        (TicketStatus.OPEN, 4),
        (TicketStatus.IN_PROGRESS, 2),
        (TicketStatus.RESOLVED, 6),
        (TicketStatus.CLOSED, 1),
    ]

    # 6. Recent sales (Order model instances)
    mock_order = MagicMock()
    mock_order.id = uuid4()
    mock_order.platform = PlatformType.TELEGRAM
    mock_order.status = OrderStatus.DELIVERED
    mock_order.total_amount = 5000
    mock_order.created_at = datetime(2026, 6, 7, 12, 0, 0)

    recent_result = MagicMock()
    recent_result.scalars.return_value.all.return_value = [mock_order]

    # Chain execute calls in order
    mock_db_session.execute = AsyncMock(
        side_effect=[
            revenue_result,
            status_result,
            platform_result,
            trend_result,
            tickets_result,
            recent_result,
        ]
    )


def test_analytics_overview_success(test_client, override_db, mock_db_session):
    """OWNER should receive a 200 with the full analytics overview payload."""
    test_client.cookies.set("access_token", "fake_access_token")
    _mock_analytics_db(mock_db_session)

    response = test_client.get("/api/analytics/overview")
    assert response.status_code == status.HTTP_200_OK

    data = response.json()
    assert "total_revenue" in data
    assert "orders_by_status" in data
    assert "platform_metrics" in data
    assert "sales_trend" in data
    assert "tickets_by_status" in data
    assert "recent_sales" in data

    assert data["total_revenue"] == 50000
    assert isinstance(data["platform_metrics"], list)
    assert isinstance(data["sales_trend"], list)
    assert isinstance(data["recent_sales"], list)


def test_analytics_overview_forbidden_for_agent(test_client, override_db, mock_auth_stub):
    """AGENT without analytics permission should receive 403."""
    test_client.cookies.set("access_token", "fake_access_token")

    # Force role to AGENT (no analytics permission)
    mock_auth_stub.VerifyAccessToken.return_value = \
        mock_auth_stub.VerifyAccessToken.return_value.__class__(
            valid=True,
            message="Token is valid",
            role="AGENT",
            user_id="22222222-3333-4444-5555-666666666666",
            organization_id="11111111-2222-3333-4444-555555555555"
        )

    response = test_client.get("/api/analytics/overview")
    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert "analytics" in response.json()["detail"].lower()


def test_analytics_overview_no_auth(test_client, override_db):
    """Unauthenticated request should receive 401."""
    # No cookie set at all
    response = test_client.get("/api/analytics/overview")
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
