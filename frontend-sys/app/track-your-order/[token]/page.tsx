import React from 'react';
import type { Metadata } from 'next';
import { AlertCircle } from 'lucide-react';
import { cacheLife, cacheTag } from 'next/cache';
import { ClientOrderTracker } from '@/components/ClientOrderTracker';

interface OrderItem {
  id: string;
  product_id: string | null;
  quantity: number;
  unit_price: number;
  snapshot: {
    name: string;
    sku?: string;
    price: number;
    currency: string;
    description?: string;
    image?: string;
  };
}

interface Order {
  id: string;
  platform: string;
  external_customer_id: string | null;
  customer_phone: string | null;
  delivery_address: string | null;
  status: 'pending' | 'dispatch' | 'delivered' | 'cancelled';
  total_amount: number;
  currency: string;
  assigned_agent_id: string | null;
  created_at: string;
  updated_at: string;
  tax_amount?: number;
  delivery_charge?: number;
  items: OrderItem[];
}

type Props = {
  params: Promise<{ token: string }>;
};

// Server-side fetching helper (cached per request lifetime)
async function getOrderData(token: string): Promise<{ order: Order | null; error: string | null }> {
  'use cache';
  cacheLife({
    stale: 10,
    revalidate: 20,
    expire: 60
  });
  cacheTag(`order-${token}`);

  try {
    const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
    const response = await fetch(`${API_BASE_URL}/api/orders/track/${token}`, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
      },
    });

    if (!response.ok) {
      const errData = await response.json().catch(() => ({}));
      return { order: null, error: errData.detail || 'Shipment not found.' };
    }

    const data = await response.json();
    if (data.success && data.order) {
      return { order: data.order, error: null };
    }
    return { order: null, error: 'Order details missing.' };
  } catch {
    return { order: null, error: 'The tracking system is currently unreachable.' };
  }
}

// 1. Dynamic SEO Metadata Generation (Server Component Only)
export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { token } = await params;
  const { order } = await getOrderData(token);

  if (!order) {
    return {
      title: 'Order Status | Sahayak AI',
      description: 'Track your shipment status in real-time.',
    };
  }

  const orderIdShort = order.id.slice(0, 8).toUpperCase();
  const itemsCount = order.items.reduce((acc, item) => acc + item.quantity, 0);
  const statusFormatted = order.status.toUpperCase();

  return {
    title: `Order #${orderIdShort} Status: ${statusFormatted} | Sahayak AI`,
    description: `Track shipment #${orderIdShort}. Current status: ${order.status}. Contains ${itemsCount} items. Placed on ${new Date(order.created_at).toLocaleDateString()}.`,
    openGraph: {
      title: `Order #${orderIdShort} Status: ${statusFormatted}`,
      description: `Track shipment #${orderIdShort}. Current status: ${order.status}. Contains ${itemsCount} items. Placed on ${new Date(order.created_at).toLocaleDateString()}.`,
      type: 'website',
    },
  };
}

// 2. Main Server Page component
export default async function PublicOrderTrackingPage({ params }: Props) {
  const { token } = await params;
  const { order, error } = await getOrderData(token);

  if (error || !order) {
    return (
      <main className="min-h-screen bg-slate-50/50 flex flex-col items-center justify-center p-4 relative overflow-hidden font-sans">
        <div className="w-full max-w-md bg-white rounded-3xl border border-rose-105 p-8 text-center flex flex-col items-center shadow-xl relative z-10">
          <div className="w-14 h-14 bg-rose-50 border border-rose-100 text-rose-600 rounded-2xl flex items-center justify-center mb-6 shadow-md">
            <AlertCircle className="w-7 h-7" />
          </div>
          <h1 className="text-slate-800 font-black text-xl tracking-tight mb-2">Tracking Code Error</h1>
          <p className="text-slate-500 text-sm mb-8 leading-relaxed font-medium">
            {error || 'We could not locate this shipment. Please verify the URL or contact the merchant.'}
          </p>
        </div>
      </main>
    );
  }

  return (
    <main className="min-h-screen bg-slate-50/40 text-slate-800 py-16 px-4 sm:px-6 lg:px-8 relative overflow-hidden font-sans">
      {/* Premium Decorative Grid / Background blobs */}
      <div className="absolute inset-0 bg-[linear-gradient(to_right,#e2e8f0_1px,transparent_1px),linear-gradient(to_bottom,#e2e8f0_1px,transparent_1px)] bg-[size:4rem_4rem] [mask-image:radial-gradient(ellipse_60%_50%_at_50%_0%,#000_70%,transparent_100%)] opacity-20 pointer-events-none" />
      <div className="absolute top-0 right-1/4 w-96 h-96 bg-indigo-200/20 rounded-full blur-3xl pointer-events-none" />
      <div className="absolute bottom-10 left-1/4 w-96 h-96 bg-purple-200/20 rounded-full blur-3xl pointer-events-none" />

      {/* Render Client Side Component */}
      <ClientOrderTracker initialOrder={order} token={token} />
    </main>
  );
}
