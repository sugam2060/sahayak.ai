import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { PlatformConnector, PlatformType, TelegramConnectorConfig } from '@/types/connectors';

const STORAGE_KEY = 'sahayak_platform_connectors';

const DEFAULT_CONNECTORS: PlatformConnector[] = [
  { id: '1', platform: 'instagram', displayName: 'Instagram', status: 'disconnected' },
  { id: '2', platform: 'tiktok', displayName: 'TikTok', status: 'disconnected' },
  { id: '3', platform: 'discord', displayName: 'Discord', status: 'disconnected' },
  { id: '4', platform: 'telegram', displayName: 'Telegram', status: 'disconnected' },
];

// Helper to load connectors from localStorage or default
const getStoredConnectors = (): PlatformConnector[] => {
  if (typeof window === 'undefined') return DEFAULT_CONNECTORS;
  const stored = localStorage.getItem(STORAGE_KEY);
  if (!stored) {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(DEFAULT_CONNECTORS));
    return DEFAULT_CONNECTORS;
  }
  try {
    return JSON.parse(stored);
  } catch {
    return DEFAULT_CONNECTORS;
  }
};

// Helper to save connectors
const saveStoredConnectors = (connectors: PlatformConnector[]) => {
  if (typeof window === 'undefined') return;
  localStorage.setItem(STORAGE_KEY, JSON.stringify(connectors));
};

// Mock delay function
const delay = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

export const useConnectors = () => {
  return useQuery<PlatformConnector[]>({
    queryKey: ['connectors'],
    queryFn: async () => {
      await delay(600); // Simulate network latency
      return getStoredConnectors();
    },
  });
};

export const useConnectOAuth = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (platform: PlatformType) => {
      await delay(1200); // Simulate OAuth authentication latency
      const connectors = getStoredConnectors();
      const updated = connectors.map((c) => {
        if (c.platform === platform) {
          return {
            ...c,
            status: 'connected' as const,
            connectedAt: new Date().toISOString(),
            username: `${platform}_merchant_store`,
          };
        }
        return c;
      });
      saveStoredConnectors(updated);
      return platform;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['connectors'] });
    },
  });
};

export const useConnectTelegram = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (config: TelegramConnectorConfig) => {
      await delay(1500); // Simulate validation and bot token registration latency
      const connectors = getStoredConnectors();
      const updated = connectors.map((c) => {
        if (c.platform === 'telegram') {
          return {
            ...c,
            status: 'connected' as const,
            connectedAt: new Date().toISOString(),
            username: config.botUsername.startsWith('@') ? config.botUsername : `@${config.botUsername}`,
          };
        }
        return c;
      });
      saveStoredConnectors(updated);
      return config;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['connectors'] });
    },
  });
};

export const useDisconnectPlatform = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (platform: PlatformType) => {
      await delay(800); // Simulate teardown latency
      const connectors = getStoredConnectors();
      const updated = connectors.map((c) => {
        if (c.platform === platform) {
          return {
            ...c,
            status: 'disconnected' as const,
            connectedAt: undefined,
            username: undefined,
          };
        }
        return c;
      });
      saveStoredConnectors(updated);
      return platform;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['connectors'] });
    },
  });
};
