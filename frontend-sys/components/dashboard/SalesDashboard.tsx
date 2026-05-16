import { DollarSign, ShoppingBag, MessageSquare, TrendingUp, BarChart3 } from 'lucide-react';
import { StatsCard } from './StatsCard';
import { ChannelPerformance } from './ChannelPerformance';

export const SalesDashboard = () => {
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
          value="NPR 1.2M" 
          icon={DollarSign}
          trend={{ value: '12%', isUp: true }}
          color="purple"
        />
        <StatsCard 
          title="Total Orders" 
          value="3,492" 
          icon={ShoppingBag}
          trend={{ value: '8%', isUp: true }}
          color="blue"
        />
        <StatsCard 
          title="Conversion Rate" 
          value="4.2%" 
          icon={TrendingUp}
          trend={{ value: '1.2%', isUp: true }}
          color="green"
        />
        <StatsCard 
          title="Conversations" 
          value="128" 
          icon={MessageSquare}
          trend={{ value: '5%', isUp: false }}
          color="amber"
        />
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
        <div className="xl:col-span-2">
          <ChannelPerformance />
        </div>
        
        <div className="bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-2xl p-5 flex flex-col items-center justify-center min-h-[300px] text-center">
          <div className="w-12 h-12 bg-zinc-50 dark:bg-zinc-800 rounded-full flex items-center justify-center text-zinc-300 mb-3">
            <BarChart3 size={24} />
          </div>
          <h3 className="text-sm font-bold text-zinc-900 dark:text-white">Growth Trends</h3>
          <p className="text-[11px] text-zinc-500 max-w-[200px] mt-1.5">
            Visual analytics and platform growth data is being compiled.
          </p>
          <div className="mt-6 flex items-end gap-1.5 h-16">
            {[30, 45, 60, 40, 80, 50, 70].map((h, i) => (
              <div 
                key={i} 
                className="w-2.5 bg-primary/20 rounded-t-sm" 
                style={{ height: `${h}%` }}
              />
            ))}
          </div>
        </div>
      </div>
    </div>
  );
};
