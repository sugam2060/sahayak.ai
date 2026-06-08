from pydantic import BaseModel
from typing import List, Dict

class PlatformMetric(BaseModel):
    platform: str
    orders: int
    revenue: int

class SalesTrendPoint(BaseModel):
    date: str
    orders: int
    revenue: int

class RecentSale(BaseModel):
    id: str
    platform: str
    status: str
    total_amount: int
    created_at: str

class AnalyticsOverviewResponse(BaseModel):
    total_revenue: int
    orders_by_status: Dict[str, int]
    platform_metrics: List[PlatformMetric]
    sales_trend: List[SalesTrendPoint]
    tickets_by_status: Dict[str, int]
    recent_sales: List[RecentSale]
