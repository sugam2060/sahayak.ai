'use client';

import React from 'react';
import { ShoppingBag, Calendar, ArrowRight } from 'lucide-react';
import { useOrders, useUpdateOrderStatus } from '@/services/api/orders';
import Link from 'next/link';

interface Order {
  id: string;
  platform: string;
  customer_phone: string | null;
  created_at: string;
  total_amount: number;
  currency: string;
  status: string;
}

const OrderStatusDropdown = ({ id, status }: { id: string; status: string }) => {
  const updateStatusMutation = useUpdateOrderStatus();

  const getStatusColor = (s: string) => {
    switch (s.toLowerCase()) {
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

  const handleChange = async (e: React.ChangeEvent<HTMLSelectElement>) => {
    try {
      await updateStatusMutation.mutateAsync({ id, status: e.target.value });
    } catch (err) {
      console.error("Failed to update status:", err);
    }
  };

  return (
    <div className="relative inline-flex items-center gap-1.5">
      <select
        value={status}
        disabled={updateStatusMutation.isPending}
        onChange={handleChange}
        className={`text-[10px] font-extrabold px-2 py-0.5 rounded-full border uppercase cursor-pointer focus:outline-none transition-all select-none
          ${getStatusColor(status)} ${updateStatusMutation.isPending ? 'opacity-50 pointer-events-none' : ''}`}
      >
        <option value="pending">Pending</option>
        <option value="dispatch">Dispatch</option>
        <option value="delivered">Delivered</option>
        <option value="cancelled">Cancelled</option>
      </select>
      {updateStatusMutation.isPending && (
        <div className="w-3 h-3 border-2 border-indigo-600 border-t-transparent rounded-full animate-spin flex-shrink-0" />
      )}
    </div>
  );
};

export const OrdersList = () => {
  const { data, isLoading, error } = useOrders();
  const orders = data as Order[] | undefined;

  if (isLoading) {
    return (
      <div className="min-h-screen bg-slate-50/50 flex flex-col items-center justify-center p-6">
        <div className="bg-white p-8 rounded-2xl border border-slate-100 shadow-xl flex flex-col items-center gap-4 max-w-sm w-full">
          <div className="w-10 h-10 border-4 border-indigo-600 border-t-transparent rounded-full animate-spin" />
          <p className="text-xs font-bold text-slate-500 animate-pulse">Loading orders list...</p>
        </div>
      </div>
    );
  }

  if (error || !orders) {
    return (
      <div className="min-h-screen bg-slate-50/50 flex flex-col items-center justify-center p-6">
        <div className="bg-white p-8 rounded-2xl border border-rose-100 shadow-xl flex flex-col items-center gap-4 max-w-sm w-full text-center">
          <div className="w-12 h-12 rounded-full bg-rose-50 flex items-center justify-center text-rose-600 font-black text-xl">!</div>
          <h3 className="text-sm font-bold text-slate-800">Failed to Load Orders</h3>
          <p className="text-xs text-slate-500">{error instanceof Error ? error.message : 'Could not retrieve orders catalog.'}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-50/30 p-6 sm:p-8 font-sans">
      <div className="max-w-5xl mx-auto space-y-6">
        {/* Header summary */}
        <div className="bg-white rounded-2xl border border-slate-100 p-6 shadow-sm flex items-center justify-between gap-4">
          <div className="space-y-1">
            <h1 className="text-xl font-black text-slate-800 flex items-center gap-2">
              <ShoppingBag className="w-5.5 h-5.5 text-indigo-600" />
              Orders Catalog
            </h1>
            <p className="text-xs text-slate-400 font-medium">
              View and manage all customer orders placed across chat platforms.
            </p>
          </div>
          <div className="bg-indigo-50 text-indigo-700 font-extrabold text-xs px-3 py-1.5 rounded-xl border border-indigo-100">
            Total Placed: {orders.length}
          </div>
        </div>

        {/* Orders list container */}
        <div className="bg-white rounded-2xl border border-slate-100 shadow-sm overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="bg-slate-50 border-b border-slate-100 text-[10px] font-bold text-slate-400 uppercase tracking-wider">
                  <th className="p-4 pl-6">Order ID</th>
                  <th className="p-4">Platform</th>
                  <th className="p-4">Customer Phone</th>
                  <th className="p-4">Date</th>
                  <th className="p-4">Total Amount</th>
                  <th className="p-4">Status</th>
                  <th className="p-4 pr-6 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 text-xs font-medium text-slate-700">
                {orders.map((order: Order) => {
                  const date = new Date(order.created_at).toLocaleDateString('en-US', {
                    month: 'short',
                    day: 'numeric',
                    year: 'numeric'
                  });

                  return (
                    <tr key={order.id} className="hover:bg-slate-50/40 transition-colors">
                      <td className="p-4 pl-6 font-mono text-[11px] text-slate-500 truncate max-w-[120px]">{order.id}</td>
                      <td className="p-4">
                        <span className="uppercase text-[10px] font-extrabold bg-indigo-50 text-indigo-600 px-2 py-0.5 rounded border border-indigo-100">
                          {order.platform}
                        </span>
                      </td>
                      <td className="p-4">{order.customer_phone || 'N/A'}</td>
                      <td className="p-4 text-slate-400 flex items-center gap-1">
                        <Calendar className="w-3.5 h-3.5 text-slate-300" />
                        {date}
                      </td>
                      <td className="p-4 font-extrabold text-slate-800">
                        {new Intl.NumberFormat('en-US', { style: 'currency', currency: order.currency }).format(order.total_amount)}
                      </td>
                      <td className="p-4">
                        <OrderStatusDropdown id={order.id} status={order.status} />
                      </td>
                      <td className="p-4 pr-6 text-right">
                        <Link 
                          href={`/orders/${order.id}`}
                          className="inline-flex items-center gap-1 text-xs font-bold text-indigo-600 hover:text-indigo-700 transition-all cursor-pointer"
                        >
                          View Details
                          <ArrowRight className="w-3.5 h-3.5" />
                        </Link>
                      </td>
                    </tr>
                  );
                })}
                {orders.length === 0 && (
                  <tr>
                    <td colSpan={7} className="text-center p-12 text-slate-400 italic">
                      No orders have been created yet.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
};
