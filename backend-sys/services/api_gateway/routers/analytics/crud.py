from datetime import datetime, timedelta, timezone
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID

from shared.database.schema import Order, OrderStatus, PlatformType, Ticket, TicketStatus

class AnalyticsService:
    @staticmethod
    async def get_overview_metrics(db: AsyncSession, org_id: UUID) -> dict:
        """
        Query and aggregate key commerce and support analytics for an organization.
        """
        # 1. Total Revenue (all non-cancelled orders)
        revenue_stmt = select(func.sum(Order.total_amount)).where(
            Order.organization_id == org_id,
            Order.status != OrderStatus.CANCELLED
        )
        revenue_res = await db.execute(revenue_stmt)
        total_revenue = revenue_res.scalar() or 0

        # 2. Orders count by status
        status_stmt = select(Order.status, func.count(Order.id)).where(
            Order.organization_id == org_id
        ).group_by(Order.status)
        status_res = await db.execute(status_stmt)
        orders_by_status = {r[0].value if hasattr(r[0], 'value') else str(r[0]): r[1] for r in status_res.all()}
        
        # Ensure standard keys are present
        for status_val in ["pending", "dispatch", "delivered", "cancelled"]:
            if status_val not in orders_by_status:
                orders_by_status[status_val] = 0

        # 3. Platform metrics
        platform_stmt = select(
            Order.platform, 
            func.count(Order.id), 
            func.sum(Order.total_amount)
        ).where(
            Order.organization_id == org_id
        ).group_by(Order.platform)
        platform_res = await db.execute(platform_stmt)
        platform_metrics = []
        for row in platform_res.all():
            platform_metrics.append({
                "platform": row[0].value if hasattr(row[0], 'value') else str(row[0]),
                "orders": row[1],
                "revenue": row[2] or 0
            })

        # 4. Daily sales trend (last 30 days)
        thirty_days_ago = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=30)
        trend_stmt = select(
            func.date(Order.created_at).label('day'),
            func.count(Order.id).label('orders'),
            func.sum(Order.total_amount).label('revenue')
        ).where(
            Order.organization_id == org_id,
            Order.created_at >= thirty_days_ago,
            Order.status != OrderStatus.CANCELLED
        ).group_by('day').order_by('day')
        
        trend_res = await db.execute(trend_stmt)
        sales_trend = []
        for row in trend_res.all():
            date_str = str(row[0]) if row[0] else ""
            sales_trend.append({
                "date": date_str,
                "orders": row[1],
                "revenue": row[2] or 0
            })

        # 5. Tickets overview
        tickets_stmt = select(Ticket.status, func.count(Ticket.id)).where(
            Ticket.organization_id == org_id
        ).group_by(Ticket.status)
        tickets_res = await db.execute(tickets_stmt)
        tickets_by_status = {r[0].value if hasattr(r[0], 'value') else str(r[0]): r[1] for r in tickets_res.all()}
        
        for t_status in ["open", "in_progress", "resolved", "closed"]:
            if t_status not in tickets_by_status:
                tickets_by_status[t_status] = 0

        # 6. Recent sales (latest 5 orders)
        recent_stmt = select(Order).where(
            Order.organization_id == org_id
        ).order_by(Order.created_at.desc()).limit(5)
        recent_res = await db.execute(recent_stmt)
        recent_sales = []
        for o in recent_res.scalars().all():
            recent_sales.append({
                "id": str(o.id),
                "platform": o.platform.value if hasattr(o.platform, 'value') else str(o.platform),
                "status": o.status.value if hasattr(o.status, 'value') else str(o.status),
                "total_amount": o.total_amount,
                "created_at": o.created_at.isoformat() if o.created_at else ""
            })

        return {
            "total_revenue": total_revenue,
            "orders_by_status": orders_by_status,
            "platform_metrics": platform_metrics,
            "sales_trend": sales_trend,
            "tickets_by_status": tickets_by_status,
            "recent_sales": recent_sales
        }
