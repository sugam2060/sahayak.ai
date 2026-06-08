'use client';

import { DollarSign, ShoppingBag, TrendingUp, Ticket, AlertCircle } from 'lucide-react';
import { StatsCard } from './StatsCard';
import { ChannelPerformance } from './ChannelPerformance';
import { useAnalyticsOverview } from '@/services/api/analytics';
import { Loader } from '@/components/ui/Loader';
import {
  ChartContainer,
  ChartTooltip,
  ChartTooltipContent,
  type ChartConfig,
} from '@/components/ui/chart';
import { AreaChart, Area, XAxis, YAxis, CartesianGrid } from 'recharts';

const trendChartConfig: ChartConfig = {
  revenue: {
    label: 'Revenue',
    color: 'hsl(262, 83%, 58%)',
  },
  orders: {
    label: 'Orders',
    color: 'hsl(210, 100%, 55%)',
  },
};

const formatCurrency = (value: number): string => {
  if (value >= 1_000_000) return `NPR ${(value / 1_000_000).toFixed(1)}M`;
  if (value >= 1_000) return `NPR ${(value / 1_000).toFixed(1)}K`;
  return `NPR ${value}`;
};

export const SalesDashboard = () => {
  const { data, isLoading, isError, error } = useAnalyticsOverview();

  if (isLoading) {
    return (
      <div className="flex-1 flex items-center justify-center min-h-[400px]">
        <Loader size="lg" text="Loading analytics" />
      </div>
    );
  }

  if (isError) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center min-h-[400px] gap-3 text-center p-6">
        <div className="w-12 h-12 bg-red-50 dark:bg-red-900/20 rounded-full flex items-center justify-center">
          <AlertCircle size={24} className="text-red-500" />
        </div>
        <h3 className="text-sm font-bold text-zinc-900 dark:text-white">Unable to load analytics</h3>
        <p className="text-xs text-zinc-500 max-w-xs">{error?.message || 'Something went wrong.'}</p>
      </div>
    );
  }

  if (!data) return null;

  const totalOrders = Object.values(data.orders_by_status).reduce((a, b) => a + b, 0);
  const deliveredOrders = data.orders_by_status['delivered'] || 0;
  const conversionRate = totalOrders > 0 ? ((deliveredOrders / totalOrders) * 100).toFixed(1) : '0';
  const totalTickets = Object.values(data.tickets_by_status).reduce((a, b) => a + b, 0);
  const openTickets = data.tickets_by_status['open'] || 0;

  return (
    <div className="space-y-6 animate-in fade-in slide-in-from-bottom-4 duration-500 max-w-[1200px] mx-auto p-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <h2 className="text-2xl font-bold text-zinc-900 dark:text-white font-heading">
            Commerce Overview
          </h2>
          <p className="text-xs text-zinc-500 mt-0.5">
            Real-time business activity for the last 30 days.
          </p>
        </div>
        <div className="flex items-center gap-2 text-[10px] font-bold text-green-600 bg-green-50 dark:bg-green-900/10 border border-green-100 dark:border-green-900/20 px-3 py-1.5 rounded-full uppercase tracking-wider self-start sm:self-center">
          <div className="w-1.5 h-1.5 bg-green-500 rounded-full animate-pulse" />
          <span>Live Sync Active</span>
        </div>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatsCard
          title="Total Revenue"
          value={formatCurrency(data.total_revenue)}
          icon={DollarSign}
          color="purple"
        />
        <StatsCard
          title="Total Orders"
          value={totalOrders.toLocaleString()}
          icon={ShoppingBag}
          color="blue"
        />
        <StatsCard
          title="Delivery Rate"
          value={`${conversionRate}%`}
          icon={TrendingUp}
          color="green"
        />
        <StatsCard
          title="Open Tickets"
          value={`${openTickets} / ${totalTickets}`}
          icon={Ticket}
          color="amber"
        />
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
        <div className="xl:col-span-2">
          <ChannelPerformance platforms={data.platform_metrics} />
        </div>

        {/* Sales Trend Chart */}
        <div className="bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-2xl p-5 min-h-[300px]">
          <div className="mb-4">
            <h3 className="text-base font-bold text-zinc-900 dark:text-white">Revenue Trend</h3>
            <p className="text-[10px] text-zinc-500 uppercase tracking-tight">Last 30 days</p>
          </div>
          {data.sales_trend.length > 0 ? (
            <ChartContainer config={trendChartConfig} className="h-[220px] w-full">
              <AreaChart data={data.sales_trend} margin={{ top: 5, right: 10, left: -20, bottom: 0 }}>
                <defs>
                  <linearGradient id="fillRevenue" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="hsl(262, 83%, 58%)" stopOpacity={0.3} />
                    <stop offset="95%" stopColor="hsl(262, 83%, 58%)" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" className="stroke-zinc-200 dark:stroke-zinc-800" />
                <XAxis
                  dataKey="date"
                  tick={{ fontSize: 10 }}
                  tickFormatter={(v) => {
                    const d = new Date(v);
                    return `${d.getMonth() + 1}/${d.getDate()}`;
                  }}
                  className="text-zinc-400"
                />
                <YAxis tick={{ fontSize: 10 }} className="text-zinc-400" />
                <ChartTooltip content={<ChartTooltipContent />} />
                <Area
                  type="monotone"
                  dataKey="revenue"
                  stroke="hsl(262, 83%, 58%)"
                  strokeWidth={2}
                  fill="url(#fillRevenue)"
                />
              </AreaChart>
            </ChartContainer>
          ) : (
            <div className="flex items-center justify-center h-[220px] text-xs text-zinc-400">
              No trend data available yet
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
