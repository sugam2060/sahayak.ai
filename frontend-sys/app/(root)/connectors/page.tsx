'use client';

import React, { useState, useEffect } from 'react';
import { toast } from 'sonner';
import { RiPlugLine } from 'react-icons/ri';
import { useSearchParams, useRouter } from 'next/navigation';
import { ConnectorCard } from '@/components/connector/ConnectorCard';
import { ConnectorConfigModal } from '@/components/connector/ConnectorConfigModal';
import { ConnectorStats } from '@/components/connector/ConnectorStats';
import { Loader } from '@/components/ui/Loader';
import {
  useConnectors,
  useConnectOAuth,
  useConnectTelegram,
  useDisconnectPlatform,
} from '@/services/api/connectors';
import { PlatformType, TelegramConnectorConfig } from '@/types/connectors';

export default function ConnectorsPage() {
  const { data: connectors, isLoading, isError, refetch } = useConnectors();
  const connectOAuth = useConnectOAuth();
  const connectTelegram = useConnectTelegram();
  const disconnectPlatform = useDisconnectPlatform();
  const searchParams = useSearchParams();
  const router = useRouter();

  const [isTelegramModalOpen, setIsTelegramModalOpen] = useState(false);
  const [activeActionPlatform, setActiveActionPlatform] = useState<PlatformType | null>(null);
  useEffect(() => {
    const status = searchParams.get('status');
    const message = searchParams.get('message');
    const platform = searchParams.get('platform');

    if (status === 'success') {
      toast.success(`Successfully connected ${platform ? platform.charAt(0).toUpperCase() + platform.slice(1) : 'platform'}!`);
      refetch();
      router.replace('/connectors');
    } else if (status === 'error') {
      toast.error(message || 'Failed to authenticate and connect platform.');
      router.replace('/connectors');
    }
  }, [searchParams, router, refetch]);

  const handleConnect = async (platform: PlatformType) => {
    if (platform === 'telegram') {
      setIsTelegramModalOpen(true);
      return;
    }

    setActiveActionPlatform(platform);
    toast.promise(
      connectOAuth.mutateAsync(platform).finally(() => {
        setActiveActionPlatform(null);
      }),
      {
        loading: `Opening ${platform.charAt(0).toUpperCase() + platform.slice(1)} OAuth window...`,
        success: `Redirecting to ${platform.charAt(0).toUpperCase() + platform.slice(1)}...`,
        error: `Failed to authenticate ${platform}. Please try again.`,
      }
    );
  };

  const handleDisconnect = async (platform: PlatformType) => {
    setActiveActionPlatform(platform);
    toast.promise(
      disconnectPlatform.mutateAsync(platform).finally(() => {
        setActiveActionPlatform(null);
      }),
      {
        loading: `Disconnecting ${platform.charAt(0).toUpperCase() + platform.slice(1)}...`,
        success: `${platform.charAt(0).toUpperCase() + platform.slice(1)} disconnected successfully.`,
        error: `Failed to disconnect ${platform}.`,
      }
    );
  };

  const handleTelegramSubmit = async (config: TelegramConnectorConfig) => {
    setActiveActionPlatform('telegram');
    await toast.promise(
      connectTelegram.mutateAsync(config).finally(() => {
        setActiveActionPlatform(null);
      }),
      {
        loading: 'Registering Telegram bot webhook and token...',
        success: `Telegram bot @${config.botUsername.replace('@', '')} connected successfully!`,
        error: 'Failed to authenticate bot token with Telegram API.',
      }
    );
  };

  const total = connectors?.length || 0;
  const connected = connectors?.filter((c) => c.status === 'connected').length || 0;
  const disconnected = connectors?.filter((c) => c.status === 'disconnected').length || 0;

  return (
    <div className="space-y-8 max-w-[1200px] mx-auto animate-in fade-in slide-in-from-bottom-4 duration-500">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 pb-6 border-b border-zinc-200/60 dark:border-zinc-800/60">
        <div>
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-lg bg-primary/10 text-primary flex items-center justify-center">
              <RiPlugLine className="size-5" />
            </div>
            <h1 className="text-2xl font-extrabold font-heading text-slate-900 dark:text-zinc-50 tracking-tight">
              Channel Connectors
            </h1>
          </div>
          <p className="text-sm text-slate-500 dark:text-zinc-400 mt-2 max-w-2xl">
            Connect and authorize your social channels to enable automated replies, customer support ticket ingest, and instant sales checkout options.
          </p>
        </div>
        
        <div className="flex items-center gap-2 bg-emerald-50 dark:bg-emerald-500/10 border border-emerald-200/50 dark:border-emerald-500/20 px-3.5 py-1.5 rounded-xl self-start sm:self-center">
          <span className="relative flex h-2 w-2">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
            <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
          </span>
          <span className="text-[10px] font-bold text-emerald-800 dark:text-emerald-400 tracking-wider uppercase font-mono">
            Live Webhooks Active
          </span>
        </div>
      </div>

      {/* Stats Cards Section */}
      <ConnectorStats
        total={total}
        connected={connected}
        disconnected={disconnected}
        isLoading={isLoading}
      />

      {/* Available Integrations Section */}
      {isLoading ? (
        <div className="flex flex-col items-center justify-center min-h-[300px] gap-3 bg-white/40 dark:bg-zinc-900/40 backdrop-blur rounded-2xl border border-zinc-200/50 dark:border-zinc-800/50 p-6">
          <Loader size="lg" text="Loading connector integrations..." />
        </div>
      ) : isError ? (
        <div className="flex flex-col items-center justify-center min-h-[300px] text-center p-6 bg-white/50 backdrop-blur rounded-2xl border border-red-100">
          <h3 className="text-lg font-bold text-red-600">Failed to load channels</h3>
          <p className="text-sm text-slate-500 max-w-md mt-2">
            We encountered an error loading your platform integrations. Please check your network and try again.
          </p>
          <button
            onClick={() => refetch()}
            className="mt-4 px-4 py-2 bg-primary text-white text-xs font-bold rounded-lg hover:bg-primary/80 transition-all uppercase tracking-wider"
          >
            Retry Load
          </button>
        </div>
      ) : (
        <div className="bg-white/40 dark:bg-zinc-900/40 backdrop-blur-md rounded-2xl border border-zinc-200/50 dark:border-zinc-800/50 p-6 shadow-sm">
          <h2 className="text-sm font-bold text-slate-800 dark:text-zinc-200 mb-2 uppercase tracking-wider font-mono">
            Available Integrations
          </h2>
          <p className="text-xs text-slate-400 dark:text-zinc-500 mb-6">
            Toggle connections by completing the authorized login process. Telegram integrations require inputting your bot&apos;s token credentials.
          </p>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
            {connectors?.map((connector) => (
              <ConnectorCard
                key={connector.id}
                connector={connector}
                onConnect={handleConnect}
                onDisconnect={handleDisconnect}
                isConnecting={false}
                isDisconnecting={disconnectPlatform.isPending && activeActionPlatform === connector.platform}
              />
            ))}
          </div>
        </div>
      )}

      {/* Telegram Config Modal */}
      <ConnectorConfigModal
        isOpen={isTelegramModalOpen}
        onClose={() => setIsTelegramModalOpen(false)}
        onSubmit={handleTelegramSubmit}
        isSubmitting={connectTelegram.isPending}
      />
    </div>
  );
}


