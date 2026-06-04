import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Conversation, SendReplyRequest } from '@/types/chats';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export const useChats = (organizationId?: string) => {
  return useQuery<{ success: boolean; chats: Conversation[] }>({
    queryKey: ['chats', organizationId],
    queryFn: async () => {
      const url = new URL(`${API_BASE_URL}/api/chats`);
      if (organizationId) {
        url.searchParams.append('organization_id', organizationId);
      }
      const response = await fetch(url.toString(), {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
        },
        credentials: 'include',
      });
      
      if (!response.ok) {
        const errData = await response.json().catch(() => ({}));
        throw new Error(errData.detail || 'Failed to retrieve active chats.');
      }
      
      return response.json();
    },
    enabled: true,
  });
};

export const useChatHistory = (platform?: string, senderId?: string | number) => {
  return useQuery<{ success: boolean; chat: Conversation }>({
    queryKey: ['chat-history', platform, senderId],
    queryFn: async () => {
      if (!platform || senderId === undefined || senderId === null) {
        throw new Error('Platform and Sender ID are required to fetch chat history.');
      }
      const response = await fetch(`${API_BASE_URL}/api/chats/${platform}/${senderId}`, {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
        },
        credentials: 'include',
      });
      
      if (!response.ok) {
        const errData = await response.json().catch(() => ({}));
        throw new Error(errData.detail || 'Failed to retrieve chat history.');
      }
      
      return response.json();
    },
    enabled: !!platform && senderId !== undefined && senderId !== null,
  });
};

export const useSendReply = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (req: SendReplyRequest) => {
      const response = await fetch(`${API_BASE_URL}/api/chats/reply`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        credentials: 'include',
        body: JSON.stringify(req),
      });

      if (!response.ok) {
        const errData = await response.json().catch(() => ({}));
        throw new Error(errData.detail || 'Failed to send reply message.');
      }

      return response.json();
    },
    onSuccess: (data, variables) => {
      // Invalidate the chat history query so it pulls the latest messages list
      queryClient.invalidateQueries({
        queryKey: ['chat-history', variables.platform, variables.sender_id],
      });
      // Also invalidate the main chats list so the last message updates
      queryClient.invalidateQueries({
        queryKey: ['chats'],
      });
    },
  });
};

export const useToggleAI = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (req: { sender_id: string | number; platform: string; ai_assigned: boolean }) => {
      const response = await fetch(`${API_BASE_URL}/api/chats/toggle-ai`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        credentials: 'include',
        body: JSON.stringify(req),
      });

      if (!response.ok) {
        const errData = await response.json().catch(() => ({}));
        throw new Error(errData.detail || 'Failed to toggle AI assignment.');
      }

      return response.json();
    },
    onSuccess: (data, variables) => {
      // Invalidate the chat history query so it pulls the updated conversation
      queryClient.invalidateQueries({
        queryKey: ['chat-history', variables.platform, variables.sender_id],
      });
      // Also invalidate the main chats list
      queryClient.invalidateQueries({
        queryKey: ['chats'],
      });
    },
  });
};

export const useMarkChatAsRead = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (req: { sender_id: string | number; platform: string }) => {
      const response = await fetch(`${API_BASE_URL}/api/chats/read`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        credentials: 'include',
        body: JSON.stringify(req),
      });

      if (!response.ok) {
        const errData = await response.json().catch(() => ({}));
        throw new Error(errData.detail || 'Failed to mark chat as read.');
      }

      return response.json();
    },
    onSuccess: (data, variables) => {
      queryClient.invalidateQueries({
        queryKey: ['chat-history', variables.platform, String(variables.sender_id)],
      });
      queryClient.invalidateQueries({
        queryKey: ['chats'],
      });
    },
  });
};
