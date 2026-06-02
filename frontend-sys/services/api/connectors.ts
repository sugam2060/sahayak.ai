import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { PlatformConnector, PlatformType, TelegramConnectorConfig } from '@/types/connectors';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export const useConnectors = () => {
  return useQuery<PlatformConnector[]>({
    queryKey: ['connectors'],
    queryFn: async () => {
      const response = await fetch(`${API_BASE_URL}/connectors`, {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
        },
        credentials: 'include',
      });
      
      if (!response.ok) {
        const errData = await response.json().catch(() => ({}));
        throw new Error(errData.detail || 'Failed to retrieve connection statuses from server.');
      }
      
      return response.json();
    },
  });
};

export const useConnectOAuth = () => {
  return useMutation({
    mutationFn: async (platform: PlatformType) => {
      const response = await fetch(`${API_BASE_URL}/connectors/oauth/url/${platform}`, {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
        },
        credentials: 'include',
      });

      if (!response.ok) {
        const errData = await response.json().catch(() => ({}));
        throw new Error(errData.detail || `Failed to generate OAuth redirect link for ${platform}.`);
      }

      const result = await response.json();
      
      if (result.success && result.url) {
        // Redirect caller browser directly to the oauth handshake endpoint
        window.location.href = result.url;
      } else {
        throw new Error('Response did not return a valid redirection URL.');
      }
      
      return result;
    },
  });
};

export const useConnectTelegram = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (config: TelegramConnectorConfig) => {
      const response = await fetch(`${API_BASE_URL}/connectors/telegram/connect`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        credentials: 'include',
        body: JSON.stringify({
          bot_username: config.botUsername,
          access_token: config.accessToken,
        }),
      });

      if (!response.ok) {
        const errData = await response.json().catch(() => ({}));
        throw new Error(errData.detail || 'Failed to authenticate Telegram credentials.');
      }

      return response.json();
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
      const response = await fetch(`${API_BASE_URL}/connectors/disconnect/${platform}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        credentials: 'include',
      });

      if (!response.ok) {
        const errData = await response.json().catch(() => ({}));
        throw new Error(errData.detail || `Failed to disconnect platform: ${platform}.`);
      }

      return response.json();
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['connectors'] });
    },
  });
};
