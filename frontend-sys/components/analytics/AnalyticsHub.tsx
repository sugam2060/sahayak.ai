'use client';

import { useAnalyticsOverview } from '@/services/api/analytics';
import { Loader } from '@/components/ui/Loader';
import { AlertCircle, DollarSign, ShoppingBag, Ticket, Package, Clock } from 'lucide-react';
import {
  ChartContainer,
  ChartTooltip,
  ChartTooltipContent,
  ChartLegend,
  ChartLegendContent,
  type ChartConfig,
} from '@/components/ui/chart';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  LineChart,
  Line,
  PieChart,
  Pie,
  Cell,
} from 'recharts';

const revenueChartConfig: ChartConfig = {
  revenue: {
    label: 'Revenue',
    color: 'hsl(262, 83%, 58%)',
  },
  orders: {
    label: 'Orders',
    color: 'hsl(210, 100%, 55%)',
  },
};

const orderStatusChartConfig: ChartConfig = {
  pending: { label: 'Pending', color: 'hsl(45, 93%, 47%)' },
  dispatch: { label: 'Dispatched', color: 'hsl(210, 100%, 55%)' },
  delivered: { label: 'Delivered', color: 'hsl(142, 71%, 45%)' },
  cancelled: { label: 'Cancelled', color: 'hsl(0, 84%, 60%)' },
};

const ticketStatusChartConfig: ChartConfig = {
  open: { label: 'Open', color: 'hsl(0, 84%, 60%)' },
  in_progress: { label: 'In Progress', color: 'hsl(45, 93%, 47%)' },
  resolved: { label: 'Resolved', color: 'hsl(142, 71%, 45%)' },
  closed: { label: 'Closed', color: 'hsl(220, 9%, 46%)' },
};

const ORDER_PIE_COLORS = ['hsl(45, 93%, 47%)', 'hsl(210, 100%, 55%)', 'hsl(142, 71%, 45%)', 'hsl(0, 84%, 60%)'];
const TICKET_PIE_COLORS = ['hsl(0, 84%, 60%)', 'hsl(45, 93%, 47%)', 'hsl(142, 71%, 45%)', 'hsl(220, 9%, 46%)'];

const formatCurrency = (value: number): string => {
  if (value >= 1_000_000) return `NPR ${(value / 1_000_000).toFixed(1)}M`;
  if (value >= 1_000) return `NPR ${(value / 1_000).toFixed(1)}K`;
  return `NPR ${value}`;
};

const StatusBadge = ({ status }: { status: string }) => {
  const colors: Record<string, string> = {
    pending: 'bg-yellow-50 text-yellow-700 dark:bg-yellow-900/20 dark:text-yellow-400',
    dispatch: 'bg-blue-50 text-blue-700 dark:bg-blue-900/20 dark:text-blue-400',
    delivered: 'bg-green-50 text-green-700 dark:bg-green-900/20 dark:text-green-400',
    cancelled: 'bg-red-50 text-red-700 dark:bg-red-900/20 dark:text-red-400',
  };
  return (
    <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider ${colors[status] || 'bg-zinc-100 text-zinc-600'}`}>
      {status}
    </span>
  );
};

export const AnalyticsHub = () => {
  const { data, isLoading, isError, error } = useAnalyticsOverview();

  if (isLoading) {
    return (
      <div className="flex-1 flex items-center justify-center min-h-[500px]">
        <Loader size="lg" text="Loading analytics" />
      </div>
    );
  }

  if (isError) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center min-h-[500px] gap-3 text-center p-6">
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
  const totalTickets = Object.values(data.tickets_by_status).reduce((a, b) => a + b, 0);

  // Prepare data for pie charts
  const orderStatusData = Object.entries(data.orders_by_status).map(([key, value]) => ({
    name: key,
    value,
  }));

  const ticketStatusData = Object.entries(data.tickets_by_status).map(([key, value]) => ({
    name: key,
    value,
  }));

  // Prepare platform data for bar chart
  const platformBarData = data.platform_metrics.map(p => ({
    platform: p.platform.charAt(0).toUpperCase() + p.platform.slice(1),
    orders: p.orders,
    revenue: p.revenue,
  }));

  return (
    <div className="space-y-6 animate-in fade-in slide-in-from-bottom-4 duration-500 max-w-[1200px] mx-auto p-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-zinc-900 dark:text-white font-heading">
            Analytics & Reports
          </h1>
          <p className="text-xs text-zinc-500 mt-0.5">
            Detailed insights into your business performance.
          </p>
        </div>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-2xl p-4 shadow-sm">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-purple-50 dark:bg-purple-900/20 flex items-center justify-center text-purple-600 dark:text-purple-400">
              <DollarSign size={20} />
            </div>
            <div>
              <p className="text-[10px] font-bold text-zinc-400 uppercase tracking-wider">Revenue</p>
              <p className="text-lg font-bold text-zinc-900 dark:text-white font-heading">{formatCurrency(data.total_revenue)}</p>
            </div>
          </div>
        </div>
        <div className="bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-2xl p-4 shadow-sm">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-blue-50 dark:bg-blue-900/20 flex items-center justify-center text-blue-600 dark:text-blue-400">
              <ShoppingBag size={20} />
            </div>
            <div>
              <p className="text-[10px] font-bold text-zinc-400 uppercase tracking-wider">Total Orders</p>
              <p className="text-lg font-bold text-zinc-900 dark:text-white font-heading">{totalOrders.toLocaleString()}</p>
            </div>
          </div>
        </div>
        <div className="bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-2xl p-4 shadow-sm">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-amber-50 dark:bg-amber-900/20 flex items-center justify-center text-amber-600 dark:text-amber-400">
              <Ticket size={20} />
            </div>
            <div>
              <p className="text-[10px] font-bold text-zinc-400 uppercase tracking-wider">Tickets</p>
              <p className="text-lg font-bold text-zinc-900 dark:text-white font-heading">{totalTickets.toLocaleString()}</p>
            </div>
          </div>
        </div>
        <div className="bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-2xl p-4 shadow-sm">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-green-50 dark:bg-green-900/20 flex items-center justify-center text-green-600 dark:text-green-400">
              <Package size={20} />
            </div>
            <div>
              <p className="text-[10px] font-bold text-zinc-400 uppercase tracking-wider">Platforms</p>
              <p className="text-lg font-bold text-zinc-900 dark:text-white font-heading">{data.platform_metrics.length}</p>
            </div>
          </div>
        </div>
      </div>

      {/* Charts Row 1: Revenue Trend + Platform Bar */}
      <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
        {/* Revenue Trend Line Chart */}
        <div className="bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-2xl p-5">
          <div className="mb-4">
            <h3 className="text-base font-bold text-zinc-900 dark:text-white">Daily Revenue Trend</h3>
            <p className="text-[10px] text-zinc-500 uppercase tracking-tight">Last 30 days</p>
          </div>
          {data.sales_trend.length > 0 ? (
            <ChartContainer config={revenueChartConfig} className="h-[280px] w-full">
              <LineChart data={data.sales_trend} margin={{ top: 5, right: 10, left: -20, bottom: 0 }}>
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
                <ChartLegend content={<ChartLegendContent />} />
                <Line
                  type="monotone"
                  dataKey="revenue"
                  stroke="hsl(262, 83%, 58%)"
                  strokeWidth={2}
                  dot={{ r: 3, fill: 'hsl(262, 83%, 58%)' }}
                  activeDot={{ r: 5 }}
                />
                <Line
                  type="monotone"
                  dataKey="orders"
                  stroke="hsl(210, 100%, 55%)"
                  strokeWidth={2}
                  dot={{ r: 3, fill: 'hsl(210, 100%, 55%)' }}
                  activeDot={{ r: 5 }}
                />
              </LineChart>
            </ChartContainer>
          ) : (
            <div className="flex items-center justify-center h-[280px] text-xs text-zinc-400">
              No trend data available yet
            </div>
          )}
        </div>

        {/* Platform Revenue Bar Chart */}
        <div className="bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-2xl p-5">
          <div className="mb-4">
            <h3 className="text-base font-bold text-zinc-900 dark:text-white">Revenue by Platform</h3>
            <p className="text-[10px] text-zinc-500 uppercase tracking-tight">Channel breakdown</p>
          </div>
          {platformBarData.length > 0 ? (
            <ChartContainer config={revenueChartConfig} className="h-[280px] w-full">
              <BarChart data={platformBarData} margin={{ top: 5, right: 10, left: -20, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" className="stroke-zinc-200 dark:stroke-zinc-800" />
                <XAxis dataKey="platform" tick={{ fontSize: 11 }} className="text-zinc-400" />
                <YAxis tick={{ fontSize: 10 }} className="text-zinc-400" />
                <ChartTooltip content={<ChartTooltipContent />} />
                <ChartLegend content={<ChartLegendContent />} />
                <Bar dataKey="revenue" fill="hsl(262, 83%, 58%)" radius={[6, 6, 0, 0]} barSize={32} />
                <Bar dataKey="orders" fill="hsl(210, 100%, 55%)" radius={[6, 6, 0, 0]} barSize={32} />
              </BarChart>
            </ChartContainer>
          ) : (
            <div className="flex items-center justify-center h-[280px] text-xs text-zinc-400">
              No platform data yet
            </div>
          )}
        </div>
      </div>

      {/* Charts Row 2: Order Status Pie + Ticket Status Pie */}
      <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
        {/* Order Status Distribution */}
        <div className="bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-2xl p-5">
          <div className="mb-4">
            <h3 className="text-base font-bold text-zinc-900 dark:text-white">Order Status Distribution</h3>
            <p className="text-[10px] text-zinc-500 uppercase tracking-tight">{totalOrders} total orders</p>
          </div>
          <div className="flex items-center gap-6">
            <ChartContainer config={orderStatusChartConfig} className="h-[200px] w-[200px] mx-auto flex-shrink-0">
              <PieChart>
                <ChartTooltip content={<ChartTooltipContent hideLabel />} />
                <Pie
                  data={orderStatusData}
                  dataKey="value"
                  nameKey="name"
                  cx="50%"
                  cy="50%"
                  innerRadius={50}
                  outerRadius={80}
                  strokeWidth={2}
                  stroke="hsl(var(--background))"
                >
                  {orderStatusData.map((_, index) => (
                    <Cell key={`cell-${index}`} fill={ORDER_PIE_COLORS[index % ORDER_PIE_COLORS.length]} />
                  ))}
                </Pie>
              </PieChart>
            </ChartContainer>
            <div className="space-y-2 flex-1">
              {orderStatusData.map((item, index) => (
                <div key={item.name} className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <div className="w-2.5 h-2.5 rounded-sm" style={{ backgroundColor: ORDER_PIE_COLORS[index % ORDER_PIE_COLORS.length] }} />
                    <span className="text-xs font-semibold text-zinc-600 dark:text-zinc-400 capitalize">{item.name}</span>
                  </div>
                  <span className="text-xs font-bold text-zinc-900 dark:text-white">{item.value}</span>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Ticket Status Distribution */}
        <div className="bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-2xl p-5">
          <div className="mb-4">
            <h3 className="text-base font-bold text-zinc-900 dark:text-white">Ticket Status Distribution</h3>
            <p className="text-[10px] text-zinc-500 uppercase tracking-tight">{totalTickets} total tickets</p>
          </div>
          <div className="flex items-center gap-6">
            <ChartContainer config={ticketStatusChartConfig} className="h-[200px] w-[200px] mx-auto flex-shrink-0">
              <PieChart>
                <ChartTooltip content={<ChartTooltipContent hideLabel />} />
                <Pie
                  data={ticketStatusData}
                  dataKey="value"
                  nameKey="name"
                  cx="50%"
                  cy="50%"
                  innerRadius={50}
                  outerRadius={80}
                  strokeWidth={2}
                  stroke="hsl(var(--background))"
                >
                  {ticketStatusData.map((_, index) => (
                    <Cell key={`cell-${index}`} fill={TICKET_PIE_COLORS[index % TICKET_PIE_COLORS.length]} />
                  ))}
                </Pie>
              </PieChart>
            </ChartContainer>
            <div className="space-y-2 flex-1">
              {ticketStatusData.map((item, index) => (
                <div key={item.name} className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <div className="w-2.5 h-2.5 rounded-sm" style={{ backgroundColor: TICKET_PIE_COLORS[index % TICKET_PIE_COLORS.length] }} />
                    <span className="text-xs font-semibold text-zinc-600 dark:text-zinc-400 capitalize">{item.name.replace('_', ' ')}</span>
                  </div>
                  <span className="text-xs font-bold text-zinc-900 dark:text-white">{item.value}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* Recent Transactions Table */}
      <div className="bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-2xl p-5">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h3 className="text-base font-bold text-zinc-900 dark:text-white">Recent Transactions</h3>
            <p className="text-[10px] text-zinc-500 uppercase tracking-tight">Latest 5 orders</p>
          </div>
          <div className="flex items-center gap-1.5 text-[10px] font-bold text-zinc-400">
            <Clock size={12} />
            <span>Real-time</span>
          </div>
        </div>

        {data.recent_sales.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full text-left">
              <thead>
                <tr className="border-b border-zinc-100 dark:border-zinc-800">
                  <th className="pb-3 text-[10px] font-bold text-zinc-400 uppercase tracking-wider">Order ID</th>
                  <th className="pb-3 text-[10px] font-bold text-zinc-400 uppercase tracking-wider">Platform</th>
                  <th className="pb-3 text-[10px] font-bold text-zinc-400 uppercase tracking-wider">Status</th>
                  <th className="pb-3 text-[10px] font-bold text-zinc-400 uppercase tracking-wider text-right">Amount</th>
                  <th className="pb-3 text-[10px] font-bold text-zinc-400 uppercase tracking-wider text-right">Date</th>
                </tr>
              </thead>
              <tbody>
                {data.recent_sales.map((sale) => (
                  <tr key={sale.id} className="border-b border-zinc-50 dark:border-zinc-800/50 hover:bg-zinc-50/50 dark:hover:bg-zinc-800/30 transition-colors">
                    <td className="py-3 text-xs font-mono font-semibold text-zinc-700 dark:text-zinc-300">
                      {sale.id.slice(0, 8)}…
                    </td>
                    <td className="py-3 text-xs font-semibold text-zinc-600 dark:text-zinc-400 capitalize">
                      {sale.platform}
                    </td>
                    <td className="py-3">
                      <StatusBadge status={sale.status} />
                    </td>
                    <td className="py-3 text-xs font-bold text-zinc-900 dark:text-white text-right">
                      {formatCurrency(sale.total_amount)}
                    </td>
                    <td className="py-3 text-xs text-zinc-500 text-right">
                      {new Date(sale.created_at).toLocaleDateString('en-US', {
                        month: 'short',
                        day: 'numeric',
                        year: 'numeric',
                      })}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="flex items-center justify-center py-12 text-xs text-zinc-400">
            No recent transactions
          </div>
        )}
      </div>
    </div>
  );
};
