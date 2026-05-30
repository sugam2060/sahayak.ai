export interface Product {
  id: string;
  organization_id: string;
  name: string;
  description: string | null;
  price: number; // in cents/subunits
  currency: string;
  stock: number;
  sku: string | null;
  image: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface CreateProductInput {
  name: string;
  description?: string;
  price: number;
  currency?: string;
  stock: number;
  sku?: string;
  image?: string;
  is_active?: boolean;
}

export interface UpdateProductInput extends Partial<CreateProductInput> {}

export interface ProductsResponse {
  success: boolean;
  products: Product[];
  next_cursor: string | null;
  has_next: boolean;
}
