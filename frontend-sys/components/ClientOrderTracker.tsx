/* eslint-disable @next/next/no-img-element */
'use client';

import React, { useState } from 'react';
import {
  Package,
  Truck,
  CheckCircle2,
  AlertCircle,
  MapPin,
  Phone,
  ShoppingBag,
  RefreshCw,
  Clock,
  Receipt,
  Printer,
  ChevronDown,
  ChevronUp,
  Mail,
  HelpCircle,
  ExternalLink,
  MessageSquare
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

interface ClientOrderTrackerProps {
  initialOrder: Order;
  token: string;
}

export function ClientOrderTracker({ initialOrder, token }: ClientOrderTrackerProps) {
  const [order, setOrder] = useState<Order>(initialOrder);
  const [error, setError] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);

  // Updates Signup State
  const [optInEmail, setOptInEmail] = useState('');
  const [optInSuccess, setOptInSuccess] = useState(false);
  const [optInLoading, setOptInLoading] = useState(false);

  // FAQ Accordion State
  const [openFaq, setOpenFaq] = useState<number | null>(null);

  const fetchOrderDetails = async () => {
    setRefreshing(true);
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
        return;
      }

      const data = await response.json();
      if (data.success && data.order) {
        setOrder(data.order);
      } else {
        setError('Order not found.');
      }
    } catch {
      setError('The tracking link is invalid or expired.');
    } finally {
      setRefreshing(false);
    }
  };

  const getStatusStep = () => {
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

  const handlePrint = () => {
    window.print();
  };

  const handleOptInSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!optInEmail) return;
    setOptInLoading(true);
    setTimeout(() => {
      setOptInLoading(false);
      setOptInSuccess(true);
      setOptInEmail('');
    }, 1200);
  };

  const faqs = [
    {
      q: "When will my package arrive?",
      a: "Depending on your location, deliveries typically take 2-4 business days. Once marked 'In Transit' (Dispatched), your courier will update the exact delivery estimate."
    },
    {
      q: "Can I update my delivery address?",
      a: "If the order status is still 'Pending', you can contact support immediately to request a change. Once the order is 'In Transit', the package routing cannot be changed."
    },
    {
      q: "What is your return policy?",
      a: "We offer a 14-day return window for unused, unopened products. Please click 'Contact Support' below or email support@sahayak.ai to begin a return claim."
    }
  ];

  if (error) {
    return (
      <div className="w-full max-w-md mx-auto bg-white rounded-3xl border border-rose-100 p-8 text-center flex flex-col items-center shadow-xl relative z-10">
        <div className="w-14 h-14 bg-rose-50 border border-rose-100 text-rose-600 rounded-2xl flex items-center justify-center mb-6 shadow-md">
          <AlertCircle className="w-7 h-7" />
        </div>
        <h1 className="text-slate-800 font-black text-xl tracking-tight mb-2">Tracking Code Error</h1>
        <p className="text-slate-500 text-sm mb-8 leading-relaxed font-medium">
          {error}
        </p>
        <button
          onClick={fetchOrderDetails}
          className="w-full py-3.5 text-xs font-bold text-white bg-indigo-600 hover:bg-indigo-700 rounded-2xl transition-all shadow-lg shadow-indigo-100 cursor-pointer active:scale-98 font-sans"
        >
          Try Refreshing Link
        </button>
      </div>
    );
  }

  const itemsTotal = order.total_amount - (order.tax_amount || 0) - (order.delivery_charge || 0);

  return (
    <div className="max-w-4xl mx-auto space-y-8 relative z-10 text-slate-800 font-sans print:bg-white print:p-0">
      
      {/* Brand Header */}
      <header className="flex items-center justify-between border-b border-slate-100 pb-6 print:border-b-0">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 bg-indigo-600 rounded-2xl flex items-center justify-center text-white font-black shadow-xl shadow-indigo-600/10 text-lg">
            S
          </div>
          <div>
            <span className="text-sm font-black text-slate-900 tracking-tight block">Sahayak AI</span>
            <span className="text-[10px] text-slate-400 font-bold block uppercase tracking-widest">Global Order Hub</span>
          </div>
        </div>

        <div className="flex items-center gap-2 print:hidden">
          <button
            onClick={handlePrint}
            className="flex items-center gap-2 px-4 py-2 bg-white border border-slate-200 hover:bg-slate-50 rounded-2xl text-xs font-bold text-slate-600 shadow-sm transition-all cursor-pointer active:scale-95"
          >
            <Printer className="w-3.5 h-3.5" />
            Print Invoice
          </button>
          
          <button
            onClick={fetchOrderDetails}
            disabled={refreshing}
            className="flex items-center gap-2 px-4 py-2 bg-white border border-slate-200 hover:bg-slate-50 rounded-2xl text-xs font-bold text-slate-600 shadow-sm transition-all cursor-pointer disabled:opacity-50 active:scale-95"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${refreshing ? 'animate-spin' : ''}`} />
            Sync Status
          </button>
        </div>
      </header>

      {/* Main Grid: Tracking Information & Sidebar Actions */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        
        {/* Left 2 Columns: Order Information & Invoice details */}
        <div className="lg:col-span-2 space-y-8">
          
          {/* Tracking Card */}
          <section className="bg-white rounded-3xl border border-slate-100 p-6 sm:p-8 space-y-8 shadow-xs relative overflow-hidden">
            {/* Subtle accent line */}
            <div className="absolute top-0 left-0 w-full h-[4px] bg-gradient-to-r from-indigo-500 via-indigo-600 to-purple-600" />
            
            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-6 border-b border-slate-50 pb-6">
              <div className="space-y-1">
                <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full bg-indigo-50 border border-indigo-100 text-[10px] text-indigo-700 font-bold uppercase tracking-wider">
                  <Clock className="w-2.5 h-2.5" /> Live Shipment
                </span>
                <h1 className="text-xl font-black text-slate-900 tracking-tight">
                  Shipment #{order.id.slice(0, 8).toUpperCase()}
                </h1>
                <p className="text-xs text-slate-400 font-medium">
                  Confirmed on {formatDate(order.created_at)}
                </p>
              </div>

              <div className="bg-slate-50 border border-slate-100 px-5 py-3 rounded-2xl text-left sm:text-right min-w-[150px]">
                <span className="text-[10px] text-slate-400 font-bold uppercase tracking-wider block mb-1">Total Paid</span>
                <span className="text-2xl font-black text-indigo-650 tracking-tight">
                  {new Intl.NumberFormat('en-US', { style: 'currency', currency: order.currency }).format(order.total_amount)}
                </span>
              </div>
            </div>

            {/* Shipment Timeline */}
            <div className="py-2">
              {order.status === 'cancelled' ? (
                <div className="flex items-center gap-4 bg-rose-50 border border-rose-100 p-5 rounded-2xl text-rose-800">
                  <AlertCircle className="w-6 h-6 flex-shrink-0 text-rose-600 animate-pulse" />
                  <div>
                    <h3 className="text-sm font-bold">This shipment was cancelled</h3>
                    <p className="text-xs text-rose-600/80 mt-1 font-medium">Please contact our support team to re-order or request a refund status.</p>
                  </div>
                </div>
              ) : (
                <div className="relative pl-8 sm:pl-0">
                  {/* Dynamic Progress Bar - Desktop Only */}
                  <div className="absolute top-[18px] left-[55px] right-[55px] h-1 bg-slate-100 -z-10 hidden sm:block">
                    <div 
                      className="h-full bg-indigo-600 transition-all duration-700 shadow-xs" 
                      style={{ width: `${((statusStep - 1) / 2) * 100}%` }}
                    />
                  </div>

                  {/* Desktop Layout */}
                  <div className="hidden sm:grid grid-cols-3 gap-4 text-center">
                    
                    {/* Step 1: Confirmed */}
                    <div className="flex flex-col items-center">
                      <div className={`w-10 h-10 rounded-full border flex items-center justify-center transition-all ${
                        statusStep >= 1 
                          ? 'bg-indigo-600 border-indigo-600 text-white shadow-lg shadow-indigo-100' 
                          : 'bg-white border-slate-200 text-slate-400'
                      }`}>
                        <ShoppingBag className="w-5 h-5" />
                      </div>
                      <h4 className={`text-xs font-black mt-3 ${statusStep >= 1 ? 'text-slate-800' : 'text-slate-400'}`}>1. Confirmed</h4>
                      <p className="text-[10px] text-slate-400 font-bold mt-1">Order processed successfully</p>
                    </div>

                    {/* Step 2: Shipped */}
                    <div className="flex flex-col items-center">
                      <div className={`w-10 h-10 rounded-full border flex items-center justify-center transition-all ${
                        statusStep >= 2 
                          ? 'bg-indigo-600 border-indigo-600 text-white shadow-lg shadow-indigo-100' 
                          : 'bg-white border-slate-200 text-slate-400'
                      }`}>
                        <Truck className="w-5 h-5" />
                      </div>
                      <h4 className={`text-xs font-black mt-3 ${statusStep >= 2 ? 'text-slate-800' : 'text-slate-400'}`}>2. In Transit</h4>
                      <p className="text-[10px] text-slate-400 font-bold mt-1">Dispatched to regional hub</p>
                    </div>

                    {/* Step 3: Delivered */}
                    <div className="flex flex-col items-center">
                      <div className={`w-10 h-10 rounded-full border flex items-center justify-center transition-all ${
                        statusStep >= 3 
                          ? 'bg-emerald-600 border-emerald-600 text-white shadow-lg shadow-emerald-100' 
                          : 'bg-white border-slate-200 text-slate-400'
                      }`}>
                        <CheckCircle2 className="w-5 h-5" />
                      </div>
                      <h4 className={`text-xs font-black mt-3 ${statusStep >= 3 ? 'text-emerald-600' : 'text-slate-400'}`}>3. Delivered</h4>
                      <p className="text-[10px] text-slate-400 font-bold mt-1">Received & signed</p>
                    </div>
                  </div>

                  {/* Mobile Layout (Vertical Timeline) */}
                  <div className="sm:hidden space-y-6 relative before:absolute before:left-[-18px] before:top-[12px] before:bottom-[12px] before:w-[2px] before:bg-slate-100">
                    <div className="flex items-start gap-3 relative">
                      <div className={`absolute left-[-26px] top-[2px] w-4 h-4 rounded-full border-2 flex items-center justify-center ${statusStep >= 1 ? 'bg-indigo-600 border-indigo-600' : 'bg-white border-slate-200'}`} />
                      <div>
                        <h4 className="text-xs font-black text-slate-800">Order Confirmed</h4>
                        <p className="text-[10px] text-slate-450 mt-0.5">Order was processed and approved.</p>
                      </div>
                    </div>

                    <div className="flex items-start gap-3 relative">
                      <div className={`absolute left-[-26px] top-[2px] w-4 h-4 rounded-full border-2 flex items-center justify-center ${statusStep >= 2 ? 'bg-indigo-600 border-indigo-600' : 'bg-white border-slate-200'}`} />
                      <div>
                        <h4 className="text-xs font-black text-slate-800">In Transit</h4>
                        <p className="text-[10px] text-slate-450 mt-0.5">Package left sorting facility.</p>
                      </div>
                    </div>

                    <div className="flex items-start gap-3 relative">
                      <div className={`absolute left-[-26px] top-[2px] w-4 h-4 rounded-full border-2 flex items-center justify-center ${statusStep >= 3 ? 'bg-emerald-600 border-emerald-600' : 'bg-white border-slate-200'}`} />
                      <div>
                        <h4 className="text-xs font-black text-slate-800">Delivered</h4>
                        <p className="text-[10px] text-slate-450 mt-0.5">Package arrived at customer location.</p>
                      </div>
                    </div>
                  </div>
                </div>
              )}
            </div>

            {/* Destination Address & Details */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 border-t border-slate-50 pt-6">
              <div className="bg-slate-50 border border-slate-100 p-5 rounded-2xl space-y-2">
                <h3 className="text-xs font-extrabold text-slate-700 flex items-center gap-2">
                  <MapPin className="w-4 h-4 text-indigo-500" />
                  Delivery Address
                </h3>
                <p className="text-xs text-slate-600 leading-relaxed font-medium">
                  {order.delivery_address || 'No address specified.'}
                </p>
              </div>

              <div className="bg-slate-50 border border-slate-100 p-5 rounded-2xl space-y-2">
                <h3 className="text-xs font-extrabold text-slate-700 flex items-center gap-2">
                  <Phone className="w-4 h-4 text-indigo-500" />
                  Contact Information
                </h3>
                <div className="space-y-1 text-xs text-slate-650 font-medium">
                  <p>Customer Phone: <span className="font-mono text-indigo-600">{order.customer_phone || 'N/A'}</span></p>
                  {order.external_customer_id && (
                    <p className="text-[9px] text-slate-400 font-bold tracking-wider block uppercase">Platform Link ID: {order.external_customer_id}</p>
                  )}
                </div>
              </div>
            </div>
          </section>

          {/* Detailed Invoice Summary */}
          <section className="bg-white rounded-3xl border border-slate-100 p-6 sm:p-8 space-y-6 shadow-xs print:shadow-none print:border-0">
            <div className="flex items-center justify-between border-b border-slate-50 pb-4">
              <h2 className="text-sm font-black text-slate-900 flex items-center gap-2">
                <Package className="w-4 h-4 text-indigo-500" />
                Items In This Package
              </h2>
              <span className="text-[10px] bg-slate-100 border border-slate-200/50 px-3 py-1 rounded-full text-slate-500 font-bold uppercase tracking-wider">
                {order.items.reduce((acc, item) => acc + item.quantity, 0)} Items
              </span>
            </div>

            <div className="divide-y divide-slate-100">
              {order.items.map((item) => (
                <div key={item.id} className="flex items-center gap-4 py-4 first:pt-0 last:pb-0 group">
                  <div className="w-14 h-14 bg-slate-50 border border-slate-100 rounded-2xl flex items-center justify-center overflow-hidden flex-shrink-0">
                    {item.snapshot.image ? (
                      <img src={item.snapshot.image} alt={item.snapshot.name} className="w-full h-full object-cover" />
                    ) : (
                      <Package className="w-6 h-6 text-slate-400" />
                    )}
                  </div>

                  <div className="flex-1 min-w-0">
                    <h4 className="text-xs font-black text-slate-800 truncate">
                      {item.snapshot.name}
                    </h4>
                    {item.snapshot.sku && (
                      <span className="text-[9px] font-mono text-slate-400 block mt-0.5 uppercase tracking-wide">SKU: {item.snapshot.sku}</span>
                    )}
                  </div>

                  <div className="text-right">
                    <span className="text-xs font-black text-slate-900 block">
                      {new Intl.NumberFormat('en-US', { style: 'currency', currency: order.currency }).format(item.unit_price * item.quantity)}
                    </span>
                    <span className="text-[10px] text-slate-400 block mt-0.5">
                      {item.quantity} × {new Intl.NumberFormat('en-US', { style: 'currency', currency: order.currency }).format(item.unit_price)}
                    </span>
                  </div>
                </div>
              ))}
            </div>

            {/* Billing Breakdown */}
            <div className="bg-slate-50 border border-slate-100 p-5 rounded-2xl space-y-3 mt-6">
              <h3 className="text-[10px] font-bold text-slate-450 uppercase tracking-widest flex items-center gap-1.5 pb-2 border-b border-slate-200">
                <Receipt className="w-3.5 h-3.5 text-slate-400" /> Billing Breakdown
              </h3>
              
              <div className="flex justify-between text-xs text-slate-650 font-medium">
                <span>Items Subtotal</span>
                <span>
                  {new Intl.NumberFormat('en-US', { style: 'currency', currency: order.currency }).format(itemsTotal)}
                </span>
              </div>
              
              <div className="flex justify-between text-xs text-slate-650 font-medium">
                <span>Estimated Tax (VAT)</span>
                <span>
                  {new Intl.NumberFormat('en-US', { style: 'currency', currency: order.currency }).format(
                    order.tax_amount || 0
                  )}
                </span>
              </div>
              
              <div className="flex justify-between text-xs text-slate-650 font-medium">
                <span>Delivery / Courier Charge</span>
                <span>
                  {order.delivery_charge && order.delivery_charge > 0 ? (
                    new Intl.NumberFormat('en-US', { style: 'currency', currency: order.currency }).format(
                      order.delivery_charge
                    )
                  ) : (
                    <span className="text-emerald-600 font-black uppercase text-[10px] tracking-wider">Free Shipping</span>
                  )}
                </span>
              </div>
              
              <div className="pt-3 border-t border-slate-200 flex justify-between text-sm text-slate-900 font-black">
                <span>Grand Total Paid</span>
                <span className="text-indigo-600 tracking-tight">
                  {new Intl.NumberFormat('en-US', { style: 'currency', currency: order.currency }).format(
                    order.total_amount
                  )}
                </span>
              </div>
            </div>
          </section>
        </div>

        {/* Right Sidebar: Opt-in, FAQs & Actions */}
        <div className="space-y-8 print:hidden">
          
          {/* Real-time SMS/Email signup */}
          <section className="bg-gradient-to-br from-indigo-650 to-indigo-700 text-white rounded-3xl p-6 space-y-4 shadow-md">
            <div className="w-10 h-10 rounded-xl bg-white/10 flex items-center justify-center">
              <Mail className="w-5 h-5 text-white" />
            </div>
            <h3 className="text-base font-black tracking-tight leading-tight">Get Realtime Updates</h3>
            <p className="text-xs text-indigo-100 leading-relaxed font-medium">
              Opt-in to receive email and SMS alerts when your package transitions from processing to shipped.
            </p>

            {optInSuccess ? (
              <div className="bg-indigo-800/40 border border-white/20 p-4 rounded-xl flex items-center gap-3 text-white">
                <CheckCircle2 className="w-5 h-5 text-indigo-200 flex-shrink-0" />
                <span className="text-xs font-bold text-indigo-50">Signed up successfully!</span>
              </div>
            ) : (
              <form onSubmit={handleOptInSubmit} className="space-y-2.5">
                <input
                  type="email"
                  required
                  placeholder="Enter your email"
                  value={optInEmail}
                  onChange={(e) => setOptInEmail(e.target.value)}
                  className="w-full px-3.5 py-2.5 text-xs text-slate-800 bg-white rounded-xl placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-indigo-400 font-medium"
                />
                <button
                  type="submit"
                  disabled={optInLoading}
                  className="w-full py-2.5 bg-indigo-900 hover:bg-indigo-950/80 rounded-xl text-xs font-black uppercase tracking-wider transition-all disabled:opacity-50 cursor-pointer active:scale-95 text-white"
                >
                  {optInLoading ? 'Joining...' : 'Activate Alerts'}
                </button>
              </form>
            )}
          </section>

          {/* Shipping Help and FAQs */}
          <section className="bg-white rounded-3xl border border-slate-100 p-6 space-y-4 shadow-xs">
            <h3 className="text-sm font-black text-slate-850 flex items-center gap-2">
              <HelpCircle className="w-4 h-4 text-indigo-500" />
              Frequently Asked Questions
            </h3>

            <div className="space-y-3">
              {faqs.map((faq, idx) => {
                const isOpen = openFaq === idx;
                return (
                  <div key={idx} className="border-b border-slate-50 pb-3 last:border-b-0 last:pb-0">
                    <button
                      onClick={() => setOpenFaq(isOpen ? null : idx)}
                      className="w-full flex items-center justify-between text-left text-xs font-bold text-slate-700 hover:text-slate-900 py-1 transition-colors"
                    >
                      <span>{faq.q}</span>
                      {isOpen ? <ChevronUp className="w-3.5 h-3.5 text-slate-400" /> : <ChevronDown className="w-3.5 h-3.5 text-slate-400" />}
                    </button>
                    {isOpen && (
                      <p className="text-[11px] text-slate-500 mt-1 leading-relaxed font-medium transition-all">
                        {faq.a}
                      </p>
                    )}
                  </div>
                );
              })}
            </div>
          </section>

          {/* Need help? Contact merchant support */}
          <section className="bg-slate-50 border border-slate-100 rounded-3xl p-6 text-center space-y-4">
            <div className="w-10 h-10 rounded-full bg-indigo-50 text-indigo-650 flex items-center justify-center mx-auto border border-indigo-100">
              <MessageSquare className="w-5 h-5" />
            </div>
            <div>
              <h4 className="text-xs font-black text-slate-850">Looking for assistance?</h4>
              <p className="text-[10px] text-slate-450 mt-1 font-medium leading-relaxed">
                Connect directly with our support desk regarding delivery issues, cancellations, or custom inquiries.
              </p>
            </div>
            <a 
              href="mailto:support@sahayak.ai?subject=Order Support Inquiry"
              className="inline-flex items-center justify-center gap-1.5 w-full py-2.5 bg-white border border-slate-200 hover:bg-slate-50 text-slate-700 text-xs font-bold rounded-xl shadow-xs transition-colors"
            >
              Contact Support Desk
              <ExternalLink className="w-3 h-3 text-slate-400" />
            </a>
          </section>
        </div>

      </div>
    </div>
  );
}
