import { LucideIcon } from 'lucide-react';
import { IconType } from 'react-icons';

interface StatsCardProps {
  title: string;
  value: string;
  icon: LucideIcon | IconType;
  trend?: {
    value: string;
    isUp: boolean;
  };
  color?: 'blue' | 'purple' | 'green' | 'amber';
}

export const StatsCard = ({ title, value, icon: Icon, trend, color = 'blue' }: StatsCardProps) => {
  const colorClasses = {
    blue: 'bg-blue-50 text-blue-600 dark:bg-blue-900/20 dark:text-blue-400',
    purple: 'bg-purple-50 text-purple-600 dark:bg-purple-900/20 dark:text-purple-400',
    green: 'bg-green-50 text-green-600 dark:bg-green-900/20 dark:text-green-400',
    amber: 'bg-amber-50 text-amber-600 dark:bg-amber-900/20 dark:text-amber-400',
  };

  return (
    <div className="bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-2xl p-4 shadow-sm hover:shadow-md transition-all duration-300">
      <div className="flex items-start justify-between">
        <div className={`w-10 h-10 rounded-xl flex items-center justify-center ${colorClasses[color]}`}>
          <Icon size={20} />
        </div>
        {trend && (
          <div className={`flex items-center px-1.5 py-0.5 rounded-lg text-[10px] font-bold ${
            trend.isUp ? 'text-green-600 bg-green-50/50' : 'text-red-600 bg-red-50/50'
          }`}>
            {trend.isUp ? '↑' : '↓'} {trend.value}
          </div>
        )}
      </div>
      <div className="mt-3">
        <p className="text-[11px] font-bold text-zinc-400 dark:text-zinc-500 uppercase tracking-wider">
          {title}
        </p>
        <h3 className="text-xl font-bold text-zinc-900 dark:text-white font-heading mt-0.5">
          {value}
        </h3>
      </div>
    </div>
  );
};
