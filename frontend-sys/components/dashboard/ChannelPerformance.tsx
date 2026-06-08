'use client';

import { TrendingUp } from 'lucide-react';
import { RiTelegramLine, RiInstagramLine, RiWhatsappLine, RiFacebookCircleLine, RiGlobalLine } from 'react-icons/ri';
import type { PlatformMetric } from '@/services/api/analytics';
import type { IconType } from 'react-icons';

const platformIcons: Record<string, { icon: IconType; color: string; bgColor: string }> = {
  telegram: {
    icon: RiTelegramLine,
    color: 'text-sky-600',
    bgColor: 'bg-sky-50 dark:bg-sky-900/20',
  },
  instagram: {
    icon: RiInstagramLine,
    color: 'text-pink-600',
    bgColor: 'bg-pink-50 dark:bg-pink-900/20',
  },
  whatsapp: {
    icon: RiWhatsappLine,
    color: 'text-green-600',
    bgColor: 'bg-green-50 dark:bg-green-900/20',
  },
  facebook: {
    icon: RiFacebookCircleLine,
    color: 'text-blue-600',
    bgColor: 'bg-blue-50 dark:bg-blue-900/20',
  },
};

const defaultPlatform = {
  icon: RiGlobalLine,
  color: 'text-zinc-600 dark:text-zinc-300',
  bgColor: 'bg-zinc-100 dark:bg-zinc-800',
};

const formatRevenue = (val: number): string => {
  if (val >= 1_000_000) return `${(val / 1_000_000).toFixed(1)}M`;
  if (val >= 1_000) return `${(val / 1_000).toFixed(1)}K`;
  return `${val}`;
};

interface ChannelPerformanceProps {
  platforms?: PlatformMetric[];
}

export const ChannelPerformance = ({ platforms = [] }: ChannelPerformanceProps) => {
  return (
    <div className="bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-2xl p-4 shadow-sm h-full">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h3 className="text-base font-bold text-zinc-900 dark:text-white">Channel Performance</h3>
          <p className="text-[10px] text-zinc-500 uppercase tracking-tight">Revenue & orders by platform</p>
        </div>
        <div className="flex items-center gap-1.5 text-[10px] font-bold text-primary">
          <TrendingUp size={12} />
          <span>{platforms.length} channels</span>
        </div>
      </div>

      {platforms.length > 0 ? (
        <div className="space-y-2">
          {platforms.map((platform) => {
            const key = platform.platform.toLowerCase();
            const config = platformIcons[key] || defaultPlatform;
            const Icon = config.icon;
            return (
              <div
                key={platform.platform}
                className="flex items-center justify-between p-2.5 rounded-xl hover:bg-zinc-50 dark:hover:bg-zinc-800/50 transition-colors border border-transparent hover:border-zinc-100 dark:hover:border-zinc-800"
              >
                <div className="flex items-center gap-3">
                  <div className={`w-8 h-8 rounded-lg flex items-center justify-center ${config.bgColor} ${config.color}`}>
                    <Icon size={16} />
                  </div>
                  <div>
                    <p className="text-sm font-bold text-zinc-900 dark:text-zinc-100 capitalize">
                      {platform.platform}
                    </p>
                    <p className="text-[10px] text-zinc-400 font-medium">
                      {platform.orders.toLocaleString()} orders
                    </p>
                  </div>
                </div>
                <div className="text-right">
                  <p className="text-sm font-bold text-zinc-900 dark:text-zinc-100">
                    {formatRevenue(platform.revenue)}
                  </p>
                </div>
              </div>
            );
          })}
        </div>
      ) : (
        <div className="flex items-center justify-center py-12 text-xs text-zinc-400">
          No platform data available yet
        </div>
      )}
    </div>
  );
};
