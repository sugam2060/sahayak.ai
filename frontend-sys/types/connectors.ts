export type PlatformType = 'tiktok' | 'instagram' | 'discord' | 'telegram';

export type ConnectorStatus = 'connected' | 'disconnected' | 'connecting';

export interface PlatformConnector {
  id: string;
  platform: PlatformType;
  displayName: string;
  status: ConnectorStatus;
  connectedAt?: string;
  username?: string;
}

export interface TelegramConnectorConfig {
  accessToken: string;
  botUsername: string;
}
