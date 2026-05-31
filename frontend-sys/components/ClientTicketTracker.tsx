'use client';

import React, { useState } from 'react';
import {
  CheckCircle2,
  AlertCircle,
  Phone,
  RefreshCw,
  Clock,
  ChevronDown,
  ChevronUp,
  HelpCircle,
  Ticket
} from 'lucide-react';
import { TicketDetail } from '@/services/api/tickets';

interface ClientTicketTrackerProps {
  initialTicket: TicketDetail;
  token: string;
}

export function ClientTicketTracker({ initialTicket, token }: ClientTicketTrackerProps) {
  const [ticket, setTicket] = useState<TicketDetail>(initialTicket);
  const [error, setError] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);

  const [optInEmail, setOptInEmail] = useState('');
  const [optInSuccess, setOptInSuccess] = useState(false);
  const [optInLoading, setOptInLoading] = useState(false);

  const [openFaq, setOpenFaq] = useState<number | null>(null);

  const fetchTicketDetails = async () => {
    setRefreshing(true);
    setError(null);

    try {
      const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
      const response = await fetch(`${API_BASE_URL}/api/tickets/track/${token}`, {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
        },
      });

      if (!response.ok) {
        const errData = await response.json().catch(() => ({}));
        setError(errData.detail || 'Failed to retrieve ticket tracking information.');
        return;
      }

      const data = await response.json();
      if (data.success && data.ticket) {
        setTicket(data.ticket);
      } else {
        setError('Ticket not found.');
      }
    } catch {
      setError('The tracking link is invalid or expired.');
    } finally {
      setRefreshing(false);
    }
  };

  const getStatusStep = () => {
    switch (ticket.status.toLowerCase()) {
      case 'open':
        return 1;
      case 'in_progress':
        return 2;
      case 'resolved':
        return 3;
      case 'closed':
        return 4;
      default:
        return 1;
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
      q: 'How long does it take to resolve a ticket?',
      a: 'We usually respond and begin investigation within 2-4 hours. Complete resolution varies depending on the issue complexity but is typically completed in under 24 hours.'
    },
    {
      q: 'How will I receive updates?',
      a: 'Any progress or replies from our support team will reflect on this tracking page in real-time. You can also sign up for email updates below.'
    },
    {
      q: 'Can I add comments to my ticket?',
      a: 'To add details, please reply directly in the chat window where you initiated this support request. The agent handling your chat will see it instantly.'
    }
  ];

  return (
    <div className="min-h-screen bg-slate-50/50 py-12 px-4 sm:px-6 lg:px-8 font-sans">
      <div className="max-w-3xl mx-auto space-y-8">
        
        {/* Top Header Card */}
        <div className="bg-white rounded-3xl p-6 sm:p-8 shadow-sm border border-slate-100/80 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-6">
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <span className="p-1.5 rounded-lg bg-indigo-50 text-indigo-600 border border-indigo-100">
                <Ticket className="w-5 h-5" />
              </span>
              <span className="text-xs font-bold uppercase tracking-wider text-slate-400">Support Ticket Status</span>
            </div>
            <h1 className="text-xl sm:text-2xl font-black text-slate-900 mt-2">
              Ticket: {ticket.title}
            </h1>
            <p className="text-xs text-slate-500 font-medium">
              Registered on {formatDate(ticket.created_at)}
            </p>
          </div>

          <div className="flex items-center gap-2 w-full sm:w-auto">
            <button
              onClick={fetchTicketDetails}
              disabled={refreshing}
              className="flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl border border-slate-200 text-slate-700 text-xs font-bold hover:bg-slate-50 active:scale-95 transition-all w-full sm:w-auto cursor-pointer disabled:opacity-50"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${refreshing ? 'animate-spin' : ''}`} />
              Refresh Status
            </button>
          </div>
        </div>

        {error && (
          <div className="p-4 rounded-2xl bg-rose-50 border border-rose-100 text-rose-700 text-xs font-semibold flex items-center gap-2">
            <AlertCircle className="w-4 h-4 flex-shrink-0" />
            {error}
          </div>
        )}

        {/* Tracking Progress Card */}
        <div className="bg-white rounded-3xl p-6 sm:p-8 shadow-sm border border-slate-100/80 space-y-8">
          <h2 className="text-sm font-bold uppercase tracking-wider text-slate-400 flex items-center gap-2">
            <Clock className="w-4 h-4 text-indigo-500" />
            Live Tracking
          </h2>

          <div className="relative flex flex-col sm:flex-row justify-between items-start sm:items-center gap-8 sm:gap-4 mt-6">
            
            {/* Horizontal Line for Desktop */}
            <div className="hidden sm:block absolute left-8 right-8 top-[17px] h-0.5 bg-slate-100 -z-0">
              <div 
                className="h-full bg-indigo-600 transition-all duration-500"
                style={{ width: `${Math.max(0, (statusStep - 1) * 33.33)}%` }}
              />
            </div>

            {/* Steps */}
            {[
              { label: 'Open', desc: 'Ticket registered' },
              { label: 'In Progress', desc: 'Under review' },
              { label: 'Resolved', desc: 'Solution provided' },
              { label: 'Closed', desc: 'Archived' }
            ].map((step, idx) => {
              const stepNum = idx + 1;
              const isCompleted = statusStep >= stepNum;
              const isActive = statusStep === stepNum;

              return (
                <div key={idx} className="flex sm:flex-col items-center gap-4 sm:gap-2 z-10 w-full sm:w-32 text-left sm:text-center">
                  <div className={`w-9 h-9 rounded-full flex items-center justify-center transition-all duration-300 font-bold border-2
                    ${isCompleted 
                      ? 'bg-indigo-600 border-indigo-600 text-white shadow-lg shadow-indigo-100' 
                      : 'bg-white border-slate-200 text-slate-400'}`}
                  >
                    {isCompleted ? <CheckCircle2 className="w-5 h-5" /> : stepNum}
                  </div>
                  <div className="space-y-0.5">
                    <div className={`text-xs font-bold ${isActive ? 'text-indigo-600' : 'text-slate-700'}`}>
                      {step.label}
                    </div>
                    <div className="text-[10px] text-slate-400 font-medium">
                      {step.desc}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Ticket Details Card */}
        <div className="bg-white rounded-3xl p-6 sm:p-8 shadow-sm border border-slate-100/80 space-y-6">
          <h2 className="text-sm font-bold uppercase tracking-wider text-slate-400 flex items-center gap-2">
            Ticket Details
          </h2>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6 text-sm divide-y md:divide-y-0 md:divide-x divide-slate-100">
            <div className="space-y-4 pr-0 md:pr-6">
              <div>
                <span className="text-xs text-slate-400 uppercase font-semibold">Priority</span>
                <p className="font-semibold text-slate-800 capitalize mt-1">{ticket.priority}</p>
              </div>
              <div>
                <span className="text-xs text-slate-400 uppercase font-semibold">Description</span>
                <p className="text-slate-600 mt-1 whitespace-pre-wrap leading-relaxed">{ticket.description}</p>
              </div>
            </div>

            <div className="space-y-4 pt-4 md:pt-0 pl-0 md:pl-6">
              <div>
                <span className="text-xs text-slate-400 uppercase font-semibold">Customer Details</span>
                <div className="mt-2 space-y-2">
                  <p className="font-semibold text-slate-800">{ticket.customer_name || 'N/A'}</p>
                  {ticket.customer_phone && (
                    <p className="text-slate-500 flex items-center gap-1.5 text-xs font-medium">
                      <Phone className="w-3.5 h-3.5 text-slate-400" />
                      {ticket.customer_phone}
                    </p>
                  )}
                </div>
              </div>
              <div>
                <span className="text-xs text-slate-400 uppercase font-semibold">Last Updated</span>
                <p className="text-slate-600 mt-1">{formatDate(ticket.updated_at)}</p>
              </div>
            </div>
          </div>
        </div>

        {/* Opt-In Subscription Card */}
        <div className="bg-gradient-to-br from-indigo-900 to-slate-900 rounded-3xl p-6 sm:p-8 shadow-xl text-white space-y-6">
          <div className="space-y-2">
            <h2 className="text-lg font-black tracking-tight">Stay Updated</h2>
            <p className="text-xs text-indigo-200 leading-relaxed max-w-lg">
              Want real-time support status updates? Enter your email address to receive immediate status changes.
            </p>
          </div>

          {optInSuccess ? (
            <div className="p-4 rounded-2xl bg-white/10 border border-white/10 text-xs font-bold text-indigo-200 animate-in fade-in zoom-in-95 duration-300">
              ✓ Successfully subscribed! You will receive email notifications for status updates.
            </div>
          ) : (
            <form onSubmit={handleOptInSubmit} className="flex flex-col sm:flex-row gap-3">
              <input
                type="email"
                required
                placeholder="Enter your email address"
                value={optInEmail}
                onChange={(e) => setOptInEmail(e.target.value)}
                className="flex-1 h-11 px-4 rounded-xl bg-white/10 border border-white/10 text-sm font-medium text-white placeholder-indigo-300 focus:outline-none focus:ring-2 focus:ring-indigo-500"
              />
              <button
                type="submit"
                disabled={optInLoading}
                className="h-11 px-6 rounded-xl bg-white text-indigo-955 text-sm font-bold hover:bg-indigo-50 active:scale-95 transition-all shadow-lg shadow-black/20 cursor-pointer disabled:opacity-50"
              >
                {optInLoading ? 'Subscribing...' : 'Subscribe'}
              </button>
            </form>
          )}
        </div>

        {/* FAQs Section */}
        <div className="space-y-4">
          <h2 className="text-xs font-bold uppercase tracking-wider text-slate-400 flex items-center gap-2">
            <HelpCircle className="w-4 h-4 text-slate-400" />
            Frequently Asked Questions
          </h2>

          <div className="space-y-2">
            {faqs.map((faq, idx) => {
              const isOpen = openFaq === idx;
              return (
                <div key={idx} className="bg-white border border-slate-100 rounded-2xl shadow-sm overflow-hidden">
                  <button
                    onClick={() => setOpenFaq(isOpen ? null : idx)}
                    className="w-full px-6 py-4 flex items-center justify-between font-bold text-slate-700 hover:bg-slate-50/50 transition-colors text-left text-xs sm:text-sm cursor-pointer"
                  >
                    <span>{faq.q}</span>
                    {isOpen ? <ChevronUp className="w-4 h-4 text-slate-400" /> : <ChevronDown className="w-4 h-4 text-slate-400" />}
                  </button>
                  {isOpen && (
                    <div className="px-6 pb-4 text-xs sm:text-sm text-slate-500 leading-relaxed border-t border-slate-50 pt-2 bg-slate-50/20">
                      {faq.a}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>

      </div>
    </div>
  );
}
