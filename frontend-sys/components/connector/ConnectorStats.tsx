'use client';

import React from 'react';
import { RiPlugLine, RiLink, RiLinkUnlink } from 'react-icons/ri';
import { StatsCard } from '@/components/dashboard';

interface ConnectorStatsProps {
  total: number;
  connected: number;
  disconnected: number;
  isLoading: boolean;
}

export const ConnectorStats: React.FC<ConnectorStatsProps> = ({
  total,
  connected,
  disconnected,
  isLoading,
}) => {
  return (
    <div className="grid grid-cols-1 sm:grid-cols-3 gap-6">
      <StatsCard
        title="Total Channels"
        value={isLoading ? '...' : String(total)}
        icon={RiPlugLine}
        color="purple"
      />
      <StatsCard
        title="Connected Channels"
        value={isLoading ? '...' : String(connected)}
        icon={RiLink}
        color="green"
      />
      <StatsCard
        title="Disconnected"
        value={isLoading ? '...' : String(disconnected)}
        icon={RiLinkUnlink}
        color="amber"
      />
    </div>
  );
};
