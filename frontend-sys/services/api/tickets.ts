import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export interface CreateTicketInput {
  title: string;
  description: string;
  priority: string;
  customer_name?: string;
  customer_phone?: string;
  assigned_agent_id?: string;
}

export interface TicketDetail {
  id: string;
  organization_id: string;
  title: string;
  description: string;
  status: string;
  priority: string;
  customer_name: string;
  customer_phone: string;
  assigned_agent_id: string;
  created_at: string;
  updated_at: string;
  tracking_token: string;
}

export interface ListTicketsFilters {
  limit?: number;
  cursor?: string;
  status?: string;
  priority?: string;
  search?: string;
}

export const useCreateTicket = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (req: CreateTicketInput) => {
      const response = await fetch(`${API_BASE_URL}/api/tickets`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        credentials: 'include',
        body: JSON.stringify(req),
      });

      if (!response.ok) {
        const errData = await response.json().catch(() => ({}));
        throw new Error(errData.detail || 'Failed to create ticket.');
      }

      return response.json();
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['tickets'] });
    },
  });
};

export const useTickets = (filters: ListTicketsFilters = {}) => {
  const queryParams = new URLSearchParams();
  if (filters.limit) queryParams.set('limit', filters.limit.toString());
  if (filters.cursor) queryParams.set('cursor', filters.cursor);
  if (filters.status && filters.status !== 'all') queryParams.set('status', filters.status);
  if (filters.priority && filters.priority !== 'all') queryParams.set('priority', filters.priority);
  if (filters.search) queryParams.set('search', filters.search);

  const queryString = queryParams.toString();
  const url = `${API_BASE_URL}/api/tickets${queryString ? `?${queryString}` : ''}`;

  return useQuery({
    queryKey: ['tickets', filters],
    queryFn: async () => {
      const response = await fetch(url, {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
        },
        credentials: 'include',
      });

      if (!response.ok) {
        const errData = await response.json().catch(() => ({}));
        throw new Error(errData.detail || 'Failed to retrieve tickets list.');
      }

      return response.json();
    },
  });
};

export const useTicket = (id: string) => {
  return useQuery({
    queryKey: ['ticket', id],
    queryFn: async () => {
      const response = await fetch(`${API_BASE_URL}/api/tickets/${id}`, {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
        },
        credentials: 'include',
      });

      if (!response.ok) {
        const errData = await response.json().catch(() => ({}));
        throw new Error(errData.detail || 'Failed to retrieve ticket details.');
      }

      const res = await response.json();
      return res.ticket as TicketDetail;
    },
    enabled: !!id,
  });
};

export const useTrackTicket = (token: string) => {
  return useQuery({
    queryKey: ['track-ticket', token],
    queryFn: async () => {
      const response = await fetch(`${API_BASE_URL}/api/tickets/track/${token}`, {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
        },
      });

      if (!response.ok) {
        const errData = await response.json().catch(() => ({}));
        throw new Error(errData.detail || 'Failed to track ticket.');
      }

      const res = await response.json();
      return res.ticket as TicketDetail;
    },
    enabled: !!token,
  });
};

export const useUpdateTicket = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({ id, status, priority }: { id: string; status?: string; priority?: string }) => {
      const response = await fetch(`${API_BASE_URL}/api/tickets/${id}`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
        },
        credentials: 'include',
        body: JSON.stringify({ status, priority }),
      });

      if (!response.ok) {
        const errData = await response.json().catch(() => ({}));
        throw new Error(errData.detail || 'Failed to update ticket.');
      }

      return response.json();
    },
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ['tickets'] });
      queryClient.invalidateQueries({ queryKey: ['ticket', variables.id] });
    },
  });
};
