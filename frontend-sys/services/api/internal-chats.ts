import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { InternalMember, InternalConversation } from '@/types/internal-chat';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export const useInternalMembers = () => {
  return useQuery<{ success: boolean; members: InternalMember[] }>({
    queryKey: ['internal-members'],
    queryFn: async () => {
      const response = await fetch(`${API_BASE_URL}/api/internal-chats/members`, {
        method: 'GET',
        credentials: 'include',
      });
      if (!response.ok) {
        const err = await response.json().catch(() => ({}));
        throw new Error(err.detail || 'Failed to fetch organization members.');
      }
      return response.json();
    },
  });
};

export const useDirectHistory = (targetUserId: string | null) => {
  return useQuery<{ success: boolean; conversation: InternalConversation }>({
    queryKey: ['internal-direct-history', targetUserId],
    queryFn: async () => {
      if (!targetUserId) throw new Error('Target user ID is required.');
      const response = await fetch(`${API_BASE_URL}/api/internal-chats/direct/history/${targetUserId}`, {
        method: 'GET',
        credentials: 'include',
      });
      if (!response.ok) {
        const err = await response.json().catch(() => ({}));
        throw new Error(err.detail || 'Failed to fetch direct chat history.');
      }
      return response.json();
    },
    enabled: !!targetUserId,
  });
};

export const useGroupChats = () => {
  return useQuery<{ success: boolean; groups: InternalConversation[] }>({
    queryKey: ['internal-groups'],
    queryFn: async () => {
      const response = await fetch(`${API_BASE_URL}/api/internal-chats/groups`, {
        method: 'GET',
        credentials: 'include',
      });
      if (!response.ok) {
        const err = await response.json().catch(() => ({}));
        throw new Error(err.detail || 'Failed to fetch group chats.');
      }
      return response.json();
    },
  });
};

export const useGroupHistory = (groupId: string | null) => {
  return useQuery<{ success: boolean; conversation: InternalConversation }>({
    queryKey: ['internal-group-history', groupId],
    queryFn: async () => {
      if (!groupId) throw new Error('Group ID is required.');
      const response = await fetch(`${API_BASE_URL}/api/internal-chats/groups/${groupId}/history`, {
        method: 'GET',
        credentials: 'include',
      });
      if (!response.ok) {
        const err = await response.json().catch(() => ({}));
        throw new Error(err.detail || 'Failed to fetch group history.');
      }
      return response.json();
    },
    enabled: !!groupId,
  });
};

export const useCreateGroup = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (req: { name: string; member_ids: string[] }) => {
      const response = await fetch(`${API_BASE_URL}/api/internal-chats/groups`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(req),
        credentials: 'include',
      });
      if (!response.ok) {
        const err = await response.json().catch(() => ({}));
        throw new Error(err.detail || 'Failed to create group.');
      }
      return response.json();
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['internal-groups'] });
    },
  });
};

export const useManageGroupMembers = (groupId: string) => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (req: { action: 'add' | 'remove'; user_id: string }) => {
      const response = await fetch(`${API_BASE_URL}/api/internal-chats/groups/${groupId}/members`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(req),
        credentials: 'include',
      });
      if (!response.ok) {
        const err = await response.json().catch(() => ({}));
        throw new Error(err.detail || 'Failed to update group membership.');
      }
      return response.json();
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['internal-group-history', groupId] });
    },
  });
};

export const useOrgHistory = () => {
  return useQuery<{ success: boolean; conversation: InternalConversation }>({
    queryKey: ['internal-org-history'],
    queryFn: async () => {
      const response = await fetch(`${API_BASE_URL}/api/internal-chats/org/history`, {
        method: 'GET',
        credentials: 'include',
      });
      if (!response.ok) {
        const err = await response.json().catch(() => ({}));
        throw new Error(err.detail || 'Failed to fetch org broadcast history.');
      }
      return response.json();
    },
  });
};

export const useRespondCustomerRequest = () => {
  return useMutation({
    mutationFn: async (req: { message_id: string; action: 'accept' | 'decline' }) => {
      const response = await fetch(`${API_BASE_URL}/api/internal-chats/customer-request/respond`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(req),
        credentials: 'include',
      });
      if (!response.ok) {
        const err = await response.json().catch(() => ({}));
        throw new Error(err.detail || 'Failed to respond to customer chat request.');
      }
      return response.json();
    },
  });
};
