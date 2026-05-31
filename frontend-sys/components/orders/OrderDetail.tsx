/* eslint-disable @next/next/no-img-element */
'use client';

import React from 'react';
import { Package, Calendar, ShoppingBag, Phone, MapPin, User, ChevronLeft } from 'lucide-react';
import { useOrder, useUpdateOrderStatus } from '@/services/api/orders';
import Link from 'next/link';

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

interface OrderDetailProps {
  id: string;
}

export const OrderDetail = ({ id }: OrderDetailProps) => {
  const { data, isLoading, error } = useOrder(id);
  const order = data as Order | undefined;
  const updateStatusMutation = useUpdateOrderStatus();

  if (isLoading) {
    return (
      <div className="min-h-screen bg-slate-50/50 flex flex-col items-center justify-center p-6">
        <div className="bg-white p-8 rounded-2xl border border-slate-100 shadow-xl flex flex-col items-center gap-4 max-w-sm w-full">
          <div className="w-10 h-10 border-4 border-indigo-600 border-t-transparent rounded-full animate-spin" />
          <p className="text-xs font-bold text-slate-500 animate-pulse">Loading order details...</p>
        </div>
      </div>
    );
  }

  if (error || !order) {
    return (
      <div className="min-h-screen bg-slate-50/50 flex flex-col items-center justify-center p-6">
        <div className="bg-white p-8 rounded-2xl border border-rose-100 shadow-xl flex flex-col items-center gap-4 max-w-sm w-full text-center">
          <div className="w-12 h-12 rounded-full bg-rose-50 flex items-center justify-center text-rose-600 font-black text-xl">!</div>
          <h3 className="text-sm font-bold text-slate-800">Failed to Load Order</h3>
          <p className="text-xs text-slate-500">{error instanceof Error ? error.message : 'Order could not be found or you lack permission.'}</p>
          <Link href="/inbox" className="mt-2 px-4 py-2 text-xs font-bold text-white bg-indigo-600 hover:bg-indigo-700 rounded-xl transition-all cursor-pointer">
            Back to Inbox
          </Link>
        </div>
      </div>
    );
  }

  const getStatusColor = (status: string) => {
    switch (status.toLowerCase()) {
      case 'pending':
        return 'bg-amber-50 text-amber-700 border-amber-200/50';
      case 'dispatch':
        return 'bg-indigo-50 text-indigo-700 border-indigo-200/50';
      case 'delivered':
        return 'bg-emerald-50 text-emerald-700 border-emerald-200/50';
      case 'cancelled':
        return 'bg-rose-50 text-rose-700 border-rose-200/50';
      default:
        return 'bg-slate-50 text-slate-700 border-slate-200/50';
    }
  };

  const formattedDate = new Date(order.created_at).toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'long',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit'
  });

  const handleStatusChange = async (e: React.ChangeEvent<HTMLSelectElement>) => {
    try {
      await updateStatusMutation.mutateAsync({ id, status: e.target.value });
    } catch (err) {
      console.error("Failed to update order status:", err);
    }
  };

  const handleCancelOrder = async () => {
    try {
      await updateStatusMutation.mutateAsync({ id, status: 'cancelled' });
    } catch (err) {
      console.error("Failed to cancel order:", err);
    }
  };

  return (
    <div className="min-h-screen bg-slate-50/30 p-6 sm:p-8 font-sans">
      <div className="max-w-4xl mx-auto space-y-6">
        {/* Back navigation */}
        <Link 
          href="/orders" 
          className="inline-flex items-center gap-1.5 text-xs font-bold text-slate-500 hover:text-indigo-600 transition-colors"
        >
          <ChevronLeft className="w-4 h-4" />
          Back to Orders Catalog
        </Link>

        {/* Top order summary card */}
        <div className="bg-white rounded-2xl border border-slate-100 p-6 shadow-sm flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div className="space-y-1.5">
            <div className="flex items-center gap-2">
              <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">Order ID</span>
              <span className="text-xs font-mono font-medium text-slate-500">{order.id}</span>
            </div>
            <h1 className="text-xl font-black text-slate-800 flex items-center gap-2">
              <ShoppingBag className="w-5.5 h-5.5 text-indigo-600" />
              Order Overview
            </h1>
            <p className="text-xs text-slate-400 flex items-center gap-1 font-medium">
              <Calendar className="w-3.5 h-3.5 text-slate-300" />
              Placed on {formattedDate}
            </p>
          </div>

          <div className="flex items-center gap-4 flex-wrap sm:flex-nowrap">
            <div className="text-right">
              <span className="text-[9px] font-bold text-slate-400 uppercase tracking-wider block">Source Platform</span>
              <span className="text-xs font-extrabold text-indigo-600 bg-indigo-50/50 border border-indigo-100 rounded-lg px-2 py-0.5 mt-0.5 inline-block uppercase">
                {order.platform}
              </span>
            </div>

            <div className="h-8 w-px bg-slate-100 hidden sm:block" />

            <div>
              <span className="text-[9px] font-bold text-slate-400 uppercase tracking-wider block">Status</span>
              <div className="relative inline-flex items-center gap-2 mt-0.5">
                <select
                  value={order.status}
                  disabled={updateStatusMutation.isPending}
                  onChange={handleStatusChange}
                  className={`text-xs font-extrabold px-2.5 py-0.5 rounded-full border shadow-sm uppercase cursor-pointer focus:outline-none transition-all
                    ${getStatusColor(order.status)} ${updateStatusMutation.isPending ? 'opacity-50 pointer-events-none' : ''}`}
                >
                  <option value="pending">Pending</option>
                  <option value="dispatch">Dispatch</option>
                  <option value="delivered">Delivered</option>
                  <option value="cancelled">Cancelled</option>
                </select>
                {updateStatusMutation.isPending && (
                  <div className="w-3 h-3 border-2 border-indigo-600 border-t-transparent rounded-full animate-spin" />
                )}
              </div>
            </div>

            {order.status !== 'cancelled' && (
              <>
                <div className="h-8 w-px bg-slate-100 hidden sm:block" />
                <button
                  type="button"
                  disabled={updateStatusMutation.isPending}
                  onClick={handleCancelOrder}
                  className="px-3 py-1 bg-rose-50 border border-rose-200 hover:bg-rose-100 text-rose-700 rounded-xl text-xs font-bold transition-all cursor-pointer disabled:opacity-50 active:scale-[0.97]"
                >
                  Cancel Order
                </button>
              </>
            )}
          </div>
        </div>

        {/* Customer & Delivery Cards */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {/* Customer info card */}
          <div className="bg-white rounded-2xl border border-slate-100 p-6 shadow-sm space-y-4">
            <h3 className="text-xs font-black text-slate-800 uppercase tracking-wider border-b border-slate-50 pb-2 flex items-center gap-2">
              <User className="w-4 h-4 text-indigo-500" />
              Customer Details
            </h3>
            <div className="space-y-3 text-xs">
              <div>
                <span className="text-[10px] font-bold text-slate-400 block mb-0.5">External Client ID</span>
                <span className="font-mono text-slate-700 font-semibold">{order.external_customer_id || 'N/A'}</span>
              </div>
              <div>
                <span className="text-[10px] font-bold text-slate-400 block mb-0.5">Contact Number</span>
                <span className="text-slate-700 font-semibold flex items-center gap-1">
                  <Phone className="w-3.5 h-3.5 text-slate-300" />
                  {order.customer_phone || 'No phone provided'}
                </span>
              </div>
            </div>
          </div>

          {/* Delivery Address card */}
          <div className="bg-white rounded-2xl border border-slate-100 p-6 shadow-sm space-y-4">
            <h3 className="text-xs font-black text-slate-800 uppercase tracking-wider border-b border-slate-50 pb-2 flex items-center gap-2">
              <MapPin className="w-4 h-4 text-teal-500" />
              Delivery Address
            </h3>
            <div className="text-xs space-y-1">
              <span className="text-[10px] font-bold text-slate-400 block mb-1">Shipping Destination</span>
              {order.delivery_address ? (
                <p className="text-slate-700 font-medium leading-relaxed bg-slate-50/50 border border-slate-100 rounded-xl p-3">
                  {order.delivery_address}
                </p>
              ) : (
                <p className="text-slate-400 italic">No delivery address specified.</p>
              )}
            </div>
          </div>
        </div>

        {/* Order Items Table */}
        <div className="bg-white rounded-2xl border border-slate-100 shadow-sm overflow-hidden">
          <div className="p-6 border-b border-slate-50">
            <h3 className="text-xs font-black text-slate-800 uppercase tracking-wider flex items-center gap-2">
              <Package className="w-4 h-4 text-amber-500" />
              Line Items ({order.items.length})
            </h3>
          </div>

          <div className="divide-y divide-slate-100">
            {order.items.map((item: OrderItem) => (
              <div key={item.id} className="p-6 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
                <div className="flex items-center gap-4 min-w-0">
                  <div className="w-14 h-14 rounded-xl bg-slate-50 border border-slate-100 flex items-center justify-center overflow-hidden flex-shrink-0">
                    {item.snapshot?.image ? (
                      <img src={item.snapshot.image} alt={item.snapshot.name} className="w-full h-full object-cover" />
                    ) : (
                      <Package className="w-6 h-6 text-slate-300" />
                    )}
                  </div>
                  <div className="min-w-0">
                    <h4 className="text-sm font-bold text-slate-800 truncate">{item.snapshot?.name || 'Unknown Product'}</h4>
                    <p className="text-[10px] font-mono text-slate-400 mt-0.5">SKU: {item.snapshot?.sku || 'N/A'}</p>
                  </div>
                </div>

                <div className="flex items-center justify-between sm:justify-end gap-6 w-full sm:w-auto">
                  <div className="text-left sm:text-right">
                    <span className="text-[10px] font-bold text-slate-400 block sm:hidden">Price</span>
                    <span className="text-xs font-medium text-slate-500">
                      {new Intl.NumberFormat('en-US', { style: 'currency', currency: order.currency }).format(item.unit_price / 100)} each
                    </span>
                  </div>

                  <div className="text-left sm:text-center min-w-[50px]">
                    <span className="text-[10px] font-bold text-slate-400 block sm:hidden">Qty</span>
                    <span className="text-xs font-bold text-slate-700 bg-slate-100 px-2 py-0.5 rounded-lg">
                      × {item.quantity}
                    </span>
                  </div>

                  <div className="text-right min-w-[80px]">
                    <span className="text-[10px] font-bold text-slate-400 block sm:hidden">Subtotal</span>
                    <span className="text-sm font-extrabold text-indigo-600">
                      {new Intl.NumberFormat('en-US', { style: 'currency', currency: order.currency }).format((item.unit_price * item.quantity) / 100)}
                    </span>
                  </div>
                </div>
              </div>
            ))}
          </div>

          {/* Grand total section */}
          <div className="bg-slate-50/50 p-6 border-t border-slate-100 flex items-center justify-between">
            <span className="text-xs font-bold text-slate-500 uppercase tracking-wider">Grand Total</span>
            <span className="text-lg font-black text-indigo-600">
              {new Intl.NumberFormat('en-US', { style: 'currency', currency: order.currency }).format(order.total_amount / 100)}
            </span>
          </div>
        </div>
      </div>
    </div>
  );
};
