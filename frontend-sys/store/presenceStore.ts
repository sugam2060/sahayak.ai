import { create } from 'zustand';

export type UserStatus = 'online' | 'away' | 'busy' | 'offline';

interface PresenceState {
  statuses: Record<string, UserStatus>;
  myStatus: 'online' | 'away' | 'busy';
  ws: WebSocket | null;
  connectPresence: (orgId: string, userId: string) => void;
  disconnectPresence: () => void;
  changeMyStatus: (status: 'online' | 'away' | 'busy') => void;
  fetchActiveUsers: () => Promise<void>;
  updateUserStatus: (userId: string, status: UserStatus) => void;
}

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
let heartbeatInterval: NodeJS.Timeout | null = null;
let reconnectTimeout: NodeJS.Timeout | null = null;
let isIntentionalDisconnect = false;

export const usePresenceStore = create<PresenceState>((set, get) => ({
  statuses: {},
  myStatus: 'online',
  ws: null,

  updateUserStatus: (userId, status) => {
    set((state) => ({
      statuses: { ...state.statuses, [userId]: status },
    }));
  },

  fetchActiveUsers: async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/presence/active`, {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
        },
        credentials: 'include',
      });
      if (response.ok) {
        const data = await response.json();
        if (data.success && Array.isArray(data.active)) {
          const newStatuses: Record<string, UserStatus> = {};
          data.active.forEach((item: { userId: string; status: UserStatus }) => {
            newStatuses[item.userId] = item.status;
          });
          set((state) => ({
            statuses: { ...state.statuses, ...newStatuses },
          }));
        }
      }
    } catch (error) {
      console.error('[Presence Store] Failed to fetch active users:', error);
    }
  },

  connectPresence: (orgId, userId) => {
    // Prevent duplicate connection attempts
    if (get().ws) return;

    isIntentionalDisconnect = false;

    const apiBaseUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
    const wsProto = apiBaseUrl.startsWith('https:') ? 'wss:' : 'ws:';
    const wsHost = apiBaseUrl.replace(/^https?:\/\//, '').replace(/\/$/, '');
    const wsUrl = `${wsProto}//${wsHost}/api/presence/ws/${orgId}?user_id=${userId}&device_type=web`;

    console.log(`[Presence WS] Connecting to: ${wsUrl}`);
    const socket = new WebSocket(wsUrl);

    socket.onopen = () => {
      console.log('[Presence WS] Connected successfully.');
      set({ ws: socket });

      // Fetch initial active users list
      get().fetchActiveUsers();

      // Clear reconnect timeouts if any
      if (reconnectTimeout) {
        clearTimeout(reconnectTimeout);
        reconnectTimeout = null;
      }

      // Start client-side heartbeat loop (every 15 seconds)
      if (heartbeatInterval) clearInterval(heartbeatInterval);
      heartbeatInterval = setInterval(() => {
        if (!document.hidden && socket.readyState === WebSocket.OPEN) {
          socket.send(JSON.stringify({ event: 'presence:heartbeat' }));
        }
      }, 15000);

      // If user had custom status, restore it upon reconnection
      const currentMyStatus = get().myStatus;
      if (currentMyStatus !== 'online') {
        socket.send(JSON.stringify({ event: 'presence:status', status: currentMyStatus }));
      }
    };

    socket.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.event === 'presence:update') {
          const { userId: eventUserId, status: eventStatus } = data;
          get().updateUserStatus(eventUserId, eventStatus);
        }
      } catch (err) {
        console.error('[Presence WS] Failed to parse socket message:', err);
      }
    };

    socket.onerror = (error) => {
      console.error('[Presence WS] Error:', error);
    };

    socket.onclose = () => {
      console.log('[Presence WS] Connection closed.');
      set({ ws: null });
      if (heartbeatInterval) {
        clearInterval(heartbeatInterval);
        heartbeatInterval = null;
      }

      // Automatically reconnect if not an intentional disconnect (e.g. logout)
      if (!isIntentionalDisconnect) {
        console.log('[Presence WS] Connection dropped. Attempting to reconnect in 5 seconds...');
        if (reconnectTimeout) clearTimeout(reconnectTimeout);
        reconnectTimeout = setTimeout(() => {
          get().connectPresence(orgId, userId);
        }, 5000);
      }
    };
  },

  disconnectPresence: () => {
    isIntentionalDisconnect = true;
    const socket = get().ws;
    if (socket) {
      socket.close();
    }
    if (heartbeatInterval) {
      clearInterval(heartbeatInterval);
      heartbeatInterval = null;
    }
    if (reconnectTimeout) {
      clearTimeout(reconnectTimeout);
      reconnectTimeout = null;
    }
    set({ ws: null, statuses: {} });
    console.log('[Presence Store] Disconnected from presence updates.');
  },

  changeMyStatus: (status) => {
    set({ myStatus: status });
    const socket = get().ws;
    if (socket && socket.readyState === WebSocket.OPEN) {
      socket.send(JSON.stringify({ event: 'presence:status', status }));
    }
  },
}));
