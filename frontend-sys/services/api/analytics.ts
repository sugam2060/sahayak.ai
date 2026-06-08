import { useQuery } from '@tanstack/react-query';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export interface PlatformMetric {
  platform: string;
  orders: number;
  revenue: number;
}

export interface SalesTrendPoint {
  date: string;
  orders: number;
  revenue: number;
}

export interface RecentSale {
  id: string;
  platform: string;
  status: string;
  total_amount: number;
  created_at: string;
}

export interface AnalyticsOverview {
  total_revenue: number;
  orders_by_status: Record<string, number>;
  platform_metrics: PlatformMetric[];
  sales_trend: SalesTrendPoint[];
  tickets_by_status: Record<string, number>;
  recent_sales: RecentSale[];
}

export const useAnalyticsOverview = () => {
  return useQuery<AnalyticsOverview>({
    queryKey: ['analytics', 'overview'],
    queryFn: async () => {
      const response = await fetch(`${API_BASE_URL}/api/analytics/overview`, {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
        },
        credentials: 'include',
      });

      if (!response.ok) {
        const errData = await response.json().catch(() => ({}));
        throw new Error(errData.detail || 'Failed to retrieve analytics overview.');
      }

      return response.json();
    },
    staleTime: 1000 * 60 * 2, // 2 minutes
    refetchInterval: 1000 * 60 * 5, // auto-refresh every 5 minutes
  });
};
