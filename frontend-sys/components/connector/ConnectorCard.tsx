'use client';

import React from 'react';
import { FaInstagram, FaDiscord, FaTelegram } from 'react-icons/fa';
import { Card, CardHeader, CardTitle, CardContent, CardFooter } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Loader } from '@/components/ui/Loader';
import { PlatformConnector, PlatformType } from '@/types/connectors';

interface ConnectorCardProps {
  connector: PlatformConnector;
  onConnect: (platform: PlatformType) => void;
  onDisconnect: (platform: PlatformType) => void;
  isConnecting: boolean;
  isDisconnecting: boolean;
}

const getPlatformConfig = (platform: PlatformType) => {
  switch (platform) {
    case 'instagram':
      return {
        icon: FaInstagram,
        brandColor: 'bg-gradient-to-tr from-[#f9ce34] via-[#ee2a7b] to-[#6228d7]',
        brandText: 'Instagram',
        description: 'Sync DMs, comments, and automate customer message replies.',
      };

    case 'discord':
      return {
        icon: FaDiscord,
        brandColor: 'bg-[#5865F2] text-white',
        brandText: 'Discord',
        description: 'Integrate merchant support channels and auto-manage tickets.',
      };
    case 'telegram':
      return {
        icon: FaTelegram,
        brandColor: 'bg-[#2AABEE] text-white',
        brandText: 'Telegram',
        description: 'Connect direct telegram chat bot messages to your sales pipeline.',
      };
    default:
      return {
        icon: FaDiscord,
        brandColor: 'bg-slate-500 text-white',
        brandText: 'Platform',
        description: 'Manage and connect channels.',
      };
  }
};

export const ConnectorCard: React.FC<ConnectorCardProps> = ({
  connector,
  onConnect,
  onDisconnect,
  isConnecting,
  isDisconnecting,
}) => {
  const { icon: Icon, brandColor, brandText, description } = getPlatformConfig(connector.platform);
  const isConnected = connector.status === 'connected';

  return (
    <Card className="relative overflow-hidden transition-all duration-300 hover:-translate-y-1.5 hover:shadow-lg bg-white/70 dark:bg-zinc-900/70 border border-zinc-200/50 dark:border-zinc-800/50 backdrop-blur-md flex flex-col justify-between min-h-[340px]">
      {/* Platform Colored Accent Bar */}
      <div className={`absolute top-0 left-0 right-0 h-1.5 ${brandColor}`} />

      {/* Stacked Header: Centered Icon and Details */}
      <CardHeader className="flex flex-col items-center gap-3 pt-8 pb-3 text-center">
        {/* Brand Icon Badge */}
        <div className={`w-14 h-14 rounded-2xl flex items-center justify-center text-white text-2xl shadow-md ${brandColor} mb-1 transition-transform duration-300 hover:scale-105`}>
          <Icon className="size-7" />
        </div>
        
        <div className="space-y-1">
          <CardTitle className="text-lg font-bold text-slate-900 dark:text-zinc-100">
            {brandText}
          </CardTitle>
          <div>
            {isConnected ? (
              <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[10px] font-semibold bg-emerald-50 dark:bg-emerald-500/10 text-emerald-700 dark:text-emerald-400 border border-emerald-200/50 dark:border-emerald-500/20">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
                Live
              </span>
            ) : (
              <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-[10px] font-semibold bg-slate-100 dark:bg-zinc-800 text-slate-600 dark:text-zinc-400 border border-slate-200 dark:border-zinc-700">
                Disconnected
              </span>
            )}
          </div>
        </div>
      </CardHeader>

      {/* Description and Metadata */}
      <CardContent className="pt-0 pb-6 px-6 text-center flex-1 flex flex-col justify-between">
        <p className="text-xs text-slate-600 dark:text-zinc-400 leading-relaxed">
          {description}
        </p>
        
        <div className="mt-4 space-y-1 min-h-[44px] flex flex-col justify-end">
          {isConnected ? (
            <div className="text-xs font-semibold text-slate-800 dark:text-zinc-200 bg-slate-50 dark:bg-zinc-800/55 py-1.5 px-3 rounded-xl border border-slate-100 dark:border-zinc-800/80 truncate max-w-full">
              @{connector.username}
            </div>
          ) : (
            <div className="text-xs text-slate-400 dark:text-zinc-500 italic">
              Not Connected
            </div>
          )}
          
          {isConnected && connector.connectedAt && (
            <div className="text-[9px] font-mono text-slate-400 dark:text-zinc-500">
              Since {new Date(connector.connectedAt).toLocaleDateString()}
            </div>
          )}
        </div>
      </CardContent>

      {/* Card Footer with Full-Width Button */}
      <CardFooter className="bg-slate-50/50 dark:bg-zinc-800/10 border-t border-zinc-100 dark:border-zinc-800 p-4">
        {isConnected ? (
          <Button
            variant="destructive"
            className="w-full font-bold shadow-sm"
            onClick={() => onDisconnect(connector.platform)}
            disabled={isDisconnecting}
          >
            {isDisconnecting ? (
              <Loader size="sm" text="Disconnecting" className="text-destructive-foreground" />
            ) : (
              'Disconnect'
            )}
          </Button>
        ) : (
          <Button
            variant="default"
            className="w-full font-bold shadow-sm"
            onClick={() => onConnect(connector.platform)}
            disabled={isConnecting}
          >
            {isConnecting ? (
              <Loader size="sm" text="Connecting" className="text-primary-foreground" />
            ) : (
              'Connect Channel'
            )}
          </Button>
        )}
      </CardFooter>
    </Card>
  );
};
