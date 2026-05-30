import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export interface AIConfig {
  id: string;
  organization_id: string;
  ai_enabled: boolean;
  auto_order_enabled: boolean;
  system_prompt: string;
  knowledge_base: string;
  created_at?: string;
  updated_at?: string;
}

export interface UpdateAIConfigInput {
  ai_enabled: boolean;
  auto_order_enabled: boolean;
  system_prompt: string;
  knowledge_base: string;
}

export const useAIConfig = () => {
  return useQuery<{ success: boolean; config: AIConfig }>({
    queryKey: ['ai-config'],
    queryFn: async () => {
      const response = await fetch(`${API_BASE_URL}/api/ai-config`, {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
        },
        credentials: 'include',
      });

      if (!response.ok) {
        const errData = await response.json().catch(() => ({}));
        throw new Error(errData.detail || 'Failed to retrieve AI configuration.');
      }

      return response.json();
    },
  });
};

export const useUpdateAIConfig = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (data: UpdateAIConfigInput) => {
      const response = await fetch(`${API_BASE_URL}/api/ai-config`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
        },
        credentials: 'include',
        body: JSON.stringify(data),
      });

      if (!response.ok) {
        const errData = await response.json().catch(() => ({}));
        throw new Error(errData.detail || 'Failed to update AI configuration.');
      }

      return response.json();
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['ai-config'] });
    },
  });
};
