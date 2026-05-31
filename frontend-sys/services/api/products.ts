import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { ProductsResponse } from '@/types/product';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

interface GetProductsParams {
  limit?: number;
  cursor?: string | null;
  search?: string;
  sku?: string;
  is_active?: boolean;
  stock_status?: 'in_stock' | 'out_of_stock';
}

export const useProducts = (params: GetProductsParams = {}) => {
  const { limit = 10, cursor = null, search = '', sku = '', is_active, stock_status } = params;
  
  return useQuery<ProductsResponse>({
    queryKey: ['products', { limit, cursor, search, sku, is_active, stock_status }],
    queryFn: async () => {
      const url = new URL(`${API_BASE_URL}/api/products`);
      url.searchParams.append('limit', limit.toString());
      if (cursor) url.searchParams.append('cursor', cursor);
      if (search) url.searchParams.append('search', search);
      if (sku) url.searchParams.append('sku', sku);
      if (is_active !== undefined) url.searchParams.append('is_active', is_active.toString());
      if (stock_status) url.searchParams.append('stock_status', stock_status);

      const response = await fetch(url.toString(), {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
        },
        credentials: 'include',
      });

      if (!response.ok) {
        const errData = await response.json().catch(() => ({}));
        throw new Error(errData.detail || 'Failed to retrieve products catalog.');
      }

      return response.json();
    },
  });
};

export const useCreateProduct = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (req: FormData) => {
      const response = await fetch(`${API_BASE_URL}/api/products`, {
        method: 'POST',
        credentials: 'include',
        body: req,
      });

      if (!response.ok) {
        const errData = await response.json().catch(() => ({}));
        throw new Error(errData.detail || 'Failed to create product.');
      }

      return response.json();
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['products'] });
    },
  });
};

export const useUpdateProduct = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({ id, data }: { id: string; data: FormData }) => {
      const response = await fetch(`${API_BASE_URL}/api/products/${id}`, {
        method: 'PUT',
        credentials: 'include',
        body: data,
      });

      if (!response.ok) {
        const errData = await response.json().catch(() => ({}));
        throw new Error(errData.detail || 'Failed to update product.');
      }

      return response.json();
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['products'] });
    },
  });
};

export const useDeleteProduct = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (id: string) => {
      const response = await fetch(`${API_BASE_URL}/api/products/${id}`, {
        method: 'DELETE',
        headers: {
          'Content-Type': 'application/json',
        },
        credentials: 'include',
      });

      if (!response.ok) {
        const errData = await response.json().catch(() => ({}));
        throw new Error(errData.detail || 'Failed to delete product.');
      }

      return response.json();
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['products'] });
    },
  });
};
