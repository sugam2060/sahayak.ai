'use client';

import React, { useEffect, useState } from 'react';
import { useParams } from 'next/navigation';
import {
  Package,
  Truck,
  CheckCircle2,
  AlertCircle,
  Calendar,
  MapPin,
  Phone,
  ShoppingBag,
  RefreshCw,
  ChevronRight
} from 'lucide-react';

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

export default function PublicOrderTrackingPage() {
  const { token } = useParams() as { token: string };
  const [order, setOrder] = useState<Order | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);

  const fetchOrderDetails = async (isRefresh = false) => {
    if (isRefresh) {
      setRefreshing(true);
    } else {
      setLoading(true);
    }
    setError(null);

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
        setError(errData.detail || 'Failed to retrieve order tracking information.');
        setLoading(false);
        setRefreshing(false);
        return;
      }

      const data = await response.json();
      if (data.success && data.order) {
        setOrder(data.order);
      } else {
        setError('Order not found.');
      }
    } catch (err: any) {
      setError('The tracking link is invalid or expired.');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    if (token) {
      fetchOrderDetails();
    }
  }, [token]);

  const getStatusStep = () => {
    if (!order) return 0;
    switch (order.status) {
      case 'pending':
        return 1;
      case 'dispatch':
        return 2;
      case 'delivered':
        return 3;
      case 'cancelled':
        return -1;
      default:
        return 0;
    }
  };

  const statusStep = getStatusStep();

  const formatDate = (dateStr: string) => {
    if (!dateStr) return '';
    const d = new Date(dateStr);
    return d.toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  if (loading) {
    return (
      <main className="min-h-screen bg-slate-50/50 flex flex-col items-center justify-center p-4">
        <div className="w-full max-w-xl bg-white rounded-3xl border border-indigo-50/50 shadow-2xl p-8 flex flex-col items-center space-y-4">
          <div className="w-12 h-12 border-4 border-indigo-600 border-t-transparent rounded-full animate-spin" />
          <h2 className="text-slate-700 font-bold text-sm">Retrieving Order Status...</h2>
          <p className="text-slate-400 text-xs">Connecting to secure fulfillment system</p>
        </div>
      </main>
    );
  }

  if (error || !order) {
    return (
      <main className="min-h-screen bg-slate-50/50 flex flex-col items-center justify-center p-4">
        <div className="w-full max-w-md bg-white rounded-3xl border border-rose-100 shadow-2xl p-8 text-center flex flex-col items-center">
          <div className="w-12 h-12 bg-rose-50 border border-rose-100 text-rose-500 rounded-2xl flex items-center justify-center mb-4">
            <AlertCircle className="w-6 h-6" />
          </div>
          <h1 className="text-slate-800 font-extrabold text-lg mb-2">Tracking Link Error</h1>
          <p className="text-slate-500 text-sm mb-6 leading-relaxed">
            {error || 'We could not load details for this tracking code. Please verify the URL or contact customer service.'}
          </p>
          <button
            onClick={() => fetchOrderDetails()}
            className="px-6 py-2.5 text-xs font-bold text-white bg-indigo-600 hover:bg-indigo-700 rounded-xl transition-all shadow-md shadow-indigo-100 cursor-pointer"
          >
            Try Again
          </button>
        </div>
      </main>
    );
  }

  return (
    <main className="min-h-screen bg-gradient-to-tr from-slate-50 via-white to-indigo-50/30 py-12 px-4 sm:px-6 lg:px-8">
      <div className="max-w-3xl mx-auto space-y-6">

        {/* Header Branding */}
        <div className="flex items-center justify-end">


          <button
            onClick={() => fetchOrderDetails(true)}
            disabled={refreshing}
            className="flex items-center gap-1.5 px-3 py-1.5 bg-white border border-slate-100 hover:border-slate-200 rounded-xl text-xs font-bold text-slate-600 shadow-sm transition-all cursor-pointer disabled:opacity-50"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${refreshing ? 'animate-spin' : ''}`} />
            Refresh Status
          </button>
        </div>

        {/* Top Status & Summary Card */}
        <section className="bg-white rounded-3xl border border-indigo-50/50 shadow-2xl p-6 sm:p-8 space-y-6 relative overflow-hidden">
          <div className="absolute top-0 left-0 w-full h-[6px] bg-gradient-to-r from-indigo-500 via-purple-500 to-indigo-600" />

          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
            <div>
              <span className="text-[10px] text-slate-400 font-bold uppercase tracking-wider block mb-1">Order Details</span>
              <h1 className="text-xl font-black text-slate-800 flex items-center gap-2">
                Order #{order.id.slice(0, 8).toUpperCase()}
              </h1>
              <div className="flex items-center gap-2 text-xs text-slate-500 mt-1 font-medium">
                <Calendar className="w-3.5 h-3.5 text-slate-400" />
                <span>Placed on {formatDate(order.created_at)}</span>
              </div>
            </div>

            <div className="text-left sm:text-right">
              <span className="text-[10px] text-slate-400 font-bold uppercase tracking-wider block mb-1">Total Payment</span>
              <span className="text-2xl font-black text-indigo-600">
                {new Intl.NumberFormat('en-US', { style: 'currency', currency: order.currency }).format(order.total_amount / 100)}
              </span>
            </div>
          </div>

          {/* Timeline Process Bar */}
          <div className="py-6 border-t border-b border-slate-50">
            {order.status === 'cancelled' ? (
              <div className="flex items-center gap-3 bg-rose-50 border border-rose-100 p-4 rounded-2xl text-rose-700">
                <AlertCircle className="w-5 h-5 flex-shrink-0" />
                <div>
                  <h3 className="text-xs font-bold">This order has been cancelled</h3>
                  <p className="text-[10px] text-rose-500 mt-0.5">Please contact the vendor or customer representative for assistance.</p>
                </div>
              </div>
            ) : (
              <div className="relative">
                {/* Horizontal line */}
                <div className="absolute top-4 left-[24px] right-[24px] h-1 bg-slate-100 -z-10 hidden sm:block">
                  <div
                    className="h-full bg-indigo-600 transition-all duration-500"
                    style={{ width: `${((statusStep - 1) / 2) * 100}%` }}
                  />
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-3 gap-6 sm:gap-0">
                  {/* Step 1: Pending */}
                  <div className="flex sm:flex-col items-center text-left sm:text-center relative">
                    <div className={`w-8 h-8 rounded-full border-2 flex items-center justify-center transition-all ${statusStep >= 1
                      ? 'bg-indigo-600 border-indigo-600 text-white shadow-lg shadow-indigo-100'
                      : 'bg-white border-slate-200 text-slate-400'
                      }`}>
                      <ShoppingBag className="w-4 h-4" />
                    </div>
                    <div className="ml-4 sm:ml-0 sm:mt-3">
                      <h4 className={`text-xs font-bold ${statusStep >= 1 ? 'text-slate-800' : 'text-slate-400'}`}>Order Received</h4>
                      <p className="text-[10px] text-slate-400 mt-0.5">Awaiting preparation</p>
                    </div>
                  </div>

                  {/* Step 2: Shipped */}
                  <div className="flex sm:flex-col items-center text-left sm:text-center relative">
                    <div className={`w-8 h-8 rounded-full border-2 flex items-center justify-center transition-all ${statusStep >= 2
                      ? 'bg-indigo-600 border-indigo-600 text-white shadow-lg shadow-indigo-100'
                      : 'bg-white border-slate-200 text-slate-400'
                      }`}>
                      <Truck className="w-4 h-4" />
                    </div>
                    <div className="ml-4 sm:ml-0 sm:mt-3">
                      <h4 className={`text-xs font-bold ${statusStep >= 2 ? 'text-slate-800' : 'text-slate-400'}`}>Dispatched</h4>
                      <p className="text-[10px] text-slate-400 mt-0.5">On the way to destination</p>
                    </div>
                  </div>

                  {/* Step 3: Delivered */}
                  <div className="flex sm:flex-col items-center text-left sm:text-center relative">
                    <div className={`w-8 h-8 rounded-full border-2 flex items-center justify-center transition-all ${statusStep >= 3
                      ? 'bg-emerald-600 border-emerald-600 text-white shadow-lg shadow-emerald-100'
                      : 'bg-white border-slate-200 text-slate-400'
                      }`}>
                      <CheckCircle2 className="w-4 h-4" />
                    </div>
                    <div className="ml-4 sm:ml-0 sm:mt-3">
                      <h4 className={`text-xs font-bold ${statusStep >= 3 ? 'text-emerald-800' : 'text-slate-400'}`}>Delivered</h4>
                      <p className="text-[10px] text-slate-400 mt-0.5">Handed over to customer</p>
                    </div>
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* Customer & Shipping Information */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6 pt-2">
            <div className="space-y-3">
              <h3 className="text-xs font-bold text-slate-700 flex items-center gap-1.5">
                <MapPin className="w-4 h-4 text-indigo-500" />
                Shipping Destination
              </h3>
              <div className="bg-slate-50/50 border border-slate-100 p-3 rounded-2xl">
                <p className="text-xs font-medium text-slate-700 leading-relaxed">
                  {order.delivery_address || 'No shipping address specified.'}
                </p>
              </div>
            </div>

            <div className="space-y-3">
              <h3 className="text-xs font-bold text-slate-700 flex items-center gap-1.5">
                <Phone className="w-4 h-4 text-indigo-500" />
                Customer Contact
              </h3>
              <div className="bg-slate-50/50 border border-slate-100 p-3 rounded-2xl">
                <p className="text-xs font-bold text-slate-700">
                  Phone: <span className="font-mono text-indigo-600">{order.customer_phone || 'N/A'}</span>
                </p>
                {order.external_customer_id && (
                  <p className="text-[10px] text-slate-400 mt-1">
                    Platform Channel ID: {order.external_customer_id}
                  </p>
                )}
              </div>
            </div>
          </div>
        </section>

        {/* Order Items Summary */}
        <section className="bg-white rounded-3xl border border-indigo-50/50 shadow-2xl p-6 sm:p-8 space-y-4">
          <h2 className="text-sm font-bold text-slate-800 flex items-center gap-2">
            <Package className="w-4 h-4 text-indigo-600" />
            Items Summary ({order.items.reduce((acc, item) => acc + item.quantity, 0)})
          </h2>

          <div className="divide-y divide-slate-100">
            {order.items.map((item) => (
              <div key={item.id} className="flex items-center gap-4 py-4 first:pt-0 last:pb-0">
                <div className="w-12 h-12 bg-slate-50 border border-slate-100 rounded-xl flex items-center justify-center overflow-hidden flex-shrink-0">
                  {item.snapshot.image ? (
                    <img src={item.snapshot.image} alt={item.snapshot.name} className="w-full h-full object-cover" />
                  ) : (
                    <Package className="w-5 h-5 text-slate-300" />
                  )}
                </div>

                <div className="flex-1 min-w-0">
                  <h4 className="text-xs font-bold text-slate-800 truncate">{item.snapshot.name}</h4>
                  {item.snapshot.sku && (
                    <span className="text-[9px] font-mono text-slate-400 block mt-0.5">SKU: {item.snapshot.sku}</span>
                  )}
                </div>

                <div className="text-right">
                  <span className="text-xs font-bold text-slate-800 block">
                    {new Intl.NumberFormat('en-US', { style: 'currency', currency: order.currency }).format((item.unit_price * item.quantity) / 100)}
                  </span>
                  <span className="text-[10px] text-slate-400 mt-0.5 block">
                    {item.quantity} × {new Intl.NumberFormat('en-US', { style: 'currency', currency: order.currency }).format(item.unit_price / 100)}
                  </span>
                </div>
              </div>
            ))}
          </div>

          {/* Pricing Breakdown */}
          <div className="bg-slate-50/50 border border-slate-100 p-4 rounded-2xl space-y-2 mt-4">
            <div className="flex justify-between text-xs text-slate-500 font-medium">
              <span>Items Total</span>
              <span>
                {new Intl.NumberFormat('en-US', { style: 'currency', currency: order.currency }).format(
                  (order.total_amount - (order.tax_amount || 0) - (order.delivery_charge || 0)) / 100
                )}
              </span>
            </div>
            <div className="flex justify-between text-xs text-slate-500 font-medium">
              <span>Tax Amount</span>
              <span>
                {new Intl.NumberFormat('en-US', { style: 'currency', currency: order.currency }).format(
                  (order.tax_amount || 0) / 100
                )}
              </span>
            </div>
            <div className="flex justify-between text-xs text-slate-500 font-medium">
              <span>Delivery Charge</span>
              <span>
                {order.delivery_charge && order.delivery_charge > 0 ? (
                  new Intl.NumberFormat('en-US', { style: 'currency', currency: order.currency }).format(
                    order.delivery_charge / 100
                  )
                ) : (
                  <span className="text-emerald-600 font-bold">Free</span>
                )}
              </span>
            </div>
            <div className="pt-2 border-t border-slate-200/50 flex justify-between text-sm text-slate-800 font-black">
              <span>Grand Total</span>
              <span className="text-indigo-600">
                {new Intl.NumberFormat('en-US', { style: 'currency', currency: order.currency }).format(
                  order.total_amount / 100
                )}
              </span>
            </div>
          </div>
        </section>

        {/* Footer info */}
        <p className="text-center text-[10px] text-slate-400 font-bold uppercase tracking-wider">
          Secured by Sahayak AI Platform &bull; Realtime Updates
        </p>
      </div>
    </main>
  );
}
