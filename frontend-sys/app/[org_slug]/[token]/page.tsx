import React from 'react';
import type { Metadata } from 'next';
import { AlertCircle } from 'lucide-react';
import { cacheLife, cacheTag } from 'next/cache';
import { SharedProductDetail } from '@/components/sharedProduct/SharedProductDetail';

interface ProductMetadata {
  brand?: string;
  color?: string;
  model?: string;
  category?: string;
  keywords?: string[];
}

interface Product {
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
  metadata?: ProductMetadata | null;
  created_at: string;
  updated_at: string;
}

type Props = {
  params: Promise<{ org_slug: string; token: string }>;
};

// Server-side fetching helper (cached per request lifetime)
async function getProductData(token: string): Promise<{ product: Product | null; error: string | null }> {
  'use cache';
  cacheLife({
    stale: 10,
    revalidate: 20,
    expire: 60
  });
  cacheTag(`product-${token}`);

  try {
    const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
    const response = await fetch(`${API_BASE_URL}/api/products/share/${token}`, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
      },
    });

    if (!response.ok) {
      const errData = await response.json().catch(() => ({}));
      return { product: null, error: errData.detail || 'Product not found.' };
    }

    const data = await response.json();
    if (data.success && data.product) {
      return { product: data.product, error: null };
    }
    return { product: null, error: 'Product details missing.' };
  } catch {
    return { product: null, error: 'The product sharing system is currently unreachable.' };
  }
}

// Dynamic SEO Metadata Generation (Server Component Only)
export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { token } = await params;
  const { product } = await getProductData(token);

  if (!product) {
    return {
      title: 'View Product | Sahayak AI',
      description: 'View product details shared with you.',
    };
  }

  return {
    title: `${product.name} | Details`,
    description: product.description || `View details for ${product.name}.`,
    openGraph: {
      title: product.name,
      description: product.description || `View details for ${product.name}.`,
      images: product.image ? [{ url: product.image }] : [],
    },
  };
}

// Main Server Page Component
export default async function SharedProductPage({ params }: Props) {
  const { token } = await params;
  const { product, error } = await getProductData(token);

  if (error || !product) {
    return (
      <main className="min-h-screen bg-slate-50 flex flex-col items-center justify-center p-4 font-sans">
        <div className="w-full max-w-md bg-white rounded-3xl border border-rose-100 p-8 text-center flex flex-col items-center shadow-xl">
          <div className="w-14 h-14 bg-rose-50 border border-rose-100 text-rose-600 rounded-2xl flex items-center justify-center mb-6 shadow-sm">
            <AlertCircle className="w-7 h-7" />
          </div>
          <h1 className="text-slate-800 font-bold text-xl mb-2">Product Link Error</h1>
          <p className="text-slate-500 text-sm mb-6 leading-relaxed">
            {error || 'We could not load this product. Please verify the link or check back later.'}
          </p>
        </div>
      </main>
    );
  }

  return (
    <main className="min-h-screen bg-slate-50 text-slate-800 py-12 px-4 sm:px-6 lg:px-8 relative overflow-hidden font-sans">
      {/* Background decorations */}
      <div className="absolute inset-0 bg-[linear-gradient(to_right,#e2e8f0_1px,transparent_1px),linear-gradient(to_bottom,#e2e8f0_1px,transparent_1px)] bg-[size:4rem_4rem] [mask-image:radial-gradient(ellipse_60%_50%_at_50%_0%,#000_70%,transparent_100%)] opacity-20 pointer-events-none" />
      <div className="absolute top-0 right-1/4 w-96 h-96 bg-indigo-200/20 rounded-full blur-3xl pointer-events-none" />
      <div className="absolute bottom-10 left-1/4 w-96 h-96 bg-purple-200/20 rounded-full blur-3xl pointer-events-none" />

      {/* Render the unified UI component */}
      <SharedProductDetail product={product} />
    </main>
  );
}
