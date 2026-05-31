'use client';

import React from 'react';
import { TicketDetail, useUpdateTicket } from '@/services/api/tickets';
import { Button } from '@/components/ui/button';
import { CheckCircle2, Clock, Copy, AlertTriangle, Activity, User, Phone, Calendar } from 'lucide-react';
import { toast } from 'sonner';

interface TicketDetailViewProps {
  ticket: TicketDetail | null;
  isLoading: boolean;
}

export function TicketDetailView({ ticket, isLoading }: TicketDetailViewProps) {
  const updateTicketMutation = useUpdateTicket();

  const handleUpdateStatus = async (newStatus: string) => {
    if (!ticket) return;
    try {
      await updateTicketMutation.mutateAsync({
        id: ticket.id,
        status: newStatus,
      });
      toast.success(`Ticket status updated to ${newStatus}.`);
    } catch (err: any) {
      toast.error(err.message || 'Failed to update ticket status.');
    }
  };

  const handleUpdatePriority = async (newPriority: string) => {
    if (!ticket) return;
    try {
      await updateTicketMutation.mutateAsync({
        id: ticket.id,
        priority: newPriority,
      });
      toast.success(`Ticket priority updated to ${newPriority}.`);
    } catch (err: any) {
      toast.error(err.message || 'Failed to update ticket priority.');
    }
  };

  const handleCopyLink = () => {
    if (!ticket) return;
    const trackingLink = `${window.location.origin}/track-your-ticket/${ticket.tracking_token}`;
    navigator.clipboard.writeText(trackingLink);
    toast.success('Tracking link copied!', {
      description: 'You can now share this URL with the customer.',
    });
  };

  if (isLoading) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center p-8 bg-slate-50/10 text-slate-500">
        <div className="w-8 h-8 border-2 border-indigo-600 border-t-transparent rounded-full animate-spin mb-3" />
        <span className="text-sm font-medium">Loading ticket details...</span>
      </div>
    );
  }

  if (!ticket) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center p-8 bg-slate-50/10 text-slate-400">
        <AlertTriangle className="w-8 h-8 text-slate-300 mb-2" />
        <span className="text-sm">Select a ticket from the queue to manage.</span>
      </div>
    );
  }

  const isUpdating = updateTicketMutation.isPending;

  const getStatusBadge = (status: string) => {
    switch (status.toLowerCase()) {
      case 'open':
        return (
          <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-rose-50 text-rose-700 border border-rose-200">
            <AlertTriangle className="w-3.5 h-3.5" />
            Open
          </span>
        );
      case 'in_progress':
        return (
          <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-blue-50 text-blue-700 border border-blue-200 animate-pulse">
            <Activity className="w-3.5 h-3.5" />
            In Progress
          </span>
        );
      case 'resolved':
        return (
          <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200">
            <CheckCircle2 className="w-3.5 h-3.5" />
            Resolved
          </span>
        );
      case 'closed':
        return (
          <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-slate-50 text-slate-700 border border-slate-200">
            <Clock className="w-3.5 h-3.5" />
            Closed
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-slate-50 text-slate-700 border border-slate-200">
            {status}
          </span>
        );
    }
  };

  return (
    <div className="flex-1 flex flex-col h-full bg-slate-50/20">
      {/* Title / Action Header */}
      <div className="p-6 border-b border-indigo-50 bg-white/40 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div className="space-y-1">
          <div className="flex items-center gap-3">
            <h1 className="text-lg sm:text-xl font-bold text-slate-800 line-clamp-1">{ticket.title}</h1>
            {getStatusBadge(ticket.status)}
          </div>
          <p className="text-xs text-slate-400">
            Ticket ID: {ticket.id}
          </p>
        </div>

        <div className="flex items-center gap-2">
          <Button
            onClick={handleCopyLink}
            variant="outline"
            size="sm"
            className="h-9 px-3 rounded-xl border-slate-200 text-slate-600 hover:bg-slate-50 font-semibold cursor-pointer"
          >
            <Copy className="w-4 h-4 mr-1.5" />
            Copy Tracking Link
          </Button>
        </div>
      </div>

      <div className="flex-1 p-6 overflow-y-auto space-y-6">
        {/* Quick Resolve Controls */}
        <div className="p-5 bg-white border border-slate-100 rounded-2xl shadow-sm space-y-4">
          <h2 className="text-xs font-bold uppercase tracking-wider text-slate-400">Action Controls</h2>
          <div className="flex flex-wrap items-center gap-3">
            {ticket.status !== 'resolved' && (
              <Button
                disabled={isUpdating}
                onClick={() => handleUpdateStatus('resolved')}
                className="h-10 px-4 rounded-xl font-semibold bg-indigo-600 text-white hover:bg-indigo-700 active:scale-95 transition-all shadow-md shadow-indigo-100 cursor-pointer disabled:opacity-50"
              >
                <CheckCircle2 className="w-4 h-4 mr-1.5" />
                Resolve Ticket
              </Button>
            )}
            {ticket.status === 'open' && (
              <Button
                disabled={isUpdating}
                onClick={() => handleUpdateStatus('in_progress')}
                variant="outline"
                className="h-10 px-4 rounded-xl font-semibold border-slate-200 text-slate-600 hover:bg-slate-50 cursor-pointer"
              >
                <Activity className="w-4 h-4 mr-1.5" />
                Mark In Progress
              </Button>
            )}
            {ticket.status !== 'closed' && (
              <Button
                disabled={isUpdating}
                onClick={() => handleUpdateStatus('closed')}
                variant="outline"
                className="h-10 px-4 rounded-xl font-semibold border-rose-100 text-rose-600 hover:bg-rose-50/50 cursor-pointer"
              >
                <Clock className="w-4 h-4 mr-1.5" />
                Close Ticket
              </Button>
            )}
            {ticket.status === 'closed' && (
              <Button
                disabled={isUpdating}
                onClick={() => handleUpdateStatus('open')}
                className="h-10 px-4 rounded-xl font-semibold bg-indigo-600 text-white hover:bg-indigo-700 active:scale-95 transition-all cursor-pointer"
              >
                <AlertTriangle className="w-4 h-4 mr-1.5" />
                Reopen Ticket
              </Button>
            )}
          </div>
        </div>

        {/* Info Grid */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {/* Main Info */}
          <div className="md:col-span-2 p-5 bg-white border border-slate-100 rounded-2xl shadow-sm space-y-4">
            <div>
              <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400">Description</span>
              <p className="text-slate-600 mt-2 whitespace-pre-wrap text-sm leading-relaxed">
                {ticket.description}
              </p>
            </div>
          </div>

          {/* Sidebar Properties */}
          <div className="space-y-6">
            {/* Priority & Agent assignment */}
            <div className="p-5 bg-white border border-slate-100 rounded-2xl shadow-sm space-y-4">
              <h3 className="text-xs font-bold uppercase tracking-wider text-slate-400">Metadata</h3>
              <div className="space-y-4">
                <div>
                  <label className="block text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-1">Priority</label>
                  <select
                    disabled={isUpdating}
                    value={ticket.priority}
                    onChange={(e) => handleUpdatePriority(e.target.value)}
                    className="w-full h-9 rounded-lg border border-slate-200 bg-white px-2.5 text-xs focus:outline-none focus:border-indigo-500 font-medium capitalize"
                  >
                    <option value="low">Low</option>
                    <option value="medium">Medium</option>
                    <option value="high">High</option>
                    <option value="urgent">Urgent</option>
                  </select>
                </div>

                <div className="pt-2 border-t border-slate-50 space-y-3">
                  <div className="flex items-center justify-between text-xs">
                    <span className="text-slate-400 font-medium flex items-center gap-1.5">
                      <Calendar className="w-3.5 h-3.5 text-slate-400" />
                      Created:
                    </span>
                    <span className="text-slate-600 font-semibold">
                      {new Date(ticket.created_at).toLocaleDateString()}
                    </span>
                  </div>
                  <div className="flex items-center justify-between text-xs">
                    <span className="text-slate-400 font-medium flex items-center gap-1.5">
                      <Calendar className="w-3.5 h-3.5 text-slate-400" />
                      Updated:
                    </span>
                    <span className="text-slate-600 font-semibold">
                      {new Date(ticket.updated_at).toLocaleDateString()}
                    </span>
                  </div>
                </div>
              </div>
            </div>

            {/* Customer profile card */}
            <div className="p-5 bg-white border border-slate-100 rounded-2xl shadow-sm space-y-4">
              <h3 className="text-xs font-bold uppercase tracking-wider text-slate-400">Customer</h3>
              <div className="space-y-3 text-xs">
                <div className="flex items-center gap-2">
                  <User className="w-4 h-4 text-slate-400" />
                  <span className="text-slate-700 font-semibold">{ticket.customer_name || 'N/A'}</span>
                </div>
                {ticket.customer_phone && (
                  <div className="flex items-center gap-2">
                    <Phone className="w-4 h-4 text-slate-400" />
                    <span className="text-slate-600 font-semibold">{ticket.customer_phone}</span>
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
