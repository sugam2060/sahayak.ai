'use client';

import React from 'react';
import { Search, AlertCircle, Clock, CheckCircle2, Activity } from 'lucide-react';
import { TicketDetail } from '@/services/api/tickets';
import { Input } from '@/components/ui/input';

interface TicketListSidebarProps {
  tickets: TicketDetail[];
  selectedId: string | null;
  onSelect: (id: string) => void;
  searchTerm: string;
  onSearchChange: (val: string) => void;
  statusFilter: string;
  onStatusChange: (val: string) => void;
  priorityFilter: string;
  onPriorityChange: (val: string) => void;
  isLoading: boolean;
}

export function TicketListSidebar({
  tickets,
  selectedId,
  onSelect,
  searchTerm,
  onSearchChange,
  statusFilter,
  onStatusChange,
  priorityFilter,
  onPriorityChange,
  isLoading,
}: TicketListSidebarProps) {
  
  const getStatusIcon = (status: string) => {
    switch (status.toLowerCase()) {
      case 'open':
        return <AlertCircle className="w-3.5 h-3.5 text-rose-500" />;
      case 'in_progress':
        return <Activity className="w-3.5 h-3.5 text-blue-500 animate-pulse" />;
      case 'resolved':
        return <CheckCircle2 className="w-3.5 h-3.5 text-emerald-500" />;
      case 'closed':
        return <Clock className="w-3.5 h-3.5 text-slate-400" />;
      default:
        return null;
    }
  };

  const getPriorityClass = (priority: string) => {
    switch (priority.toLowerCase()) {
      case 'low':
        return 'text-slate-500 bg-slate-50 border-slate-100';
      case 'medium':
        return 'text-amber-600 bg-amber-50 border-amber-100';
      case 'high':
        return 'text-orange-600 bg-orange-50 border-orange-100';
      case 'urgent':
        return 'text-rose-600 bg-rose-50 border-rose-100';
      default:
        return 'text-slate-500 bg-slate-50';
    }
  };

  return (
    <div className="w-full md:w-80 flex-shrink-0 border-r border-indigo-50 bg-white/80 backdrop-blur-md flex flex-col h-full">
      {/* Header / Title */}
      <div className="p-4 border-b border-indigo-50">
        <h2 className="text-sm font-bold text-slate-900 uppercase tracking-wider">Tickets Queue</h2>
      </div>

      {/* Search & Filters */}
      <div className="p-4 space-y-3 border-b border-indigo-50">
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400 w-3.5 h-3.5" />
          <Input
            placeholder="Search tickets..."
            value={searchTerm}
            onChange={(e) => onSearchChange(e.target.value)}
            className="pl-9 h-9 border-slate-100 focus:border-indigo-500 text-xs bg-slate-50/50"
          />
        </div>

        <div className="grid grid-cols-2 gap-2">
          <select
            value={statusFilter}
            onChange={(e) => onStatusChange(e.target.value)}
            className="h-8 rounded-lg border border-slate-100 bg-slate-50/50 px-2 text-xs focus:outline-none focus:border-indigo-500 text-slate-600 font-medium"
          >
            <option value="all">All Statuses</option>
            <option value="open">Open</option>
            <option value="in_progress">In Progress</option>
            <option value="resolved">Resolved</option>
            <option value="closed">Closed</option>
          </select>

          <select
            value={priorityFilter}
            onChange={(e) => onPriorityChange(e.target.value)}
            className="h-8 rounded-lg border border-slate-100 bg-slate-50/50 px-2 text-xs focus:outline-none focus:border-indigo-500 text-slate-600 font-medium"
          >
            <option value="all">All Priorities</option>
            <option value="low">Low</option>
            <option value="medium">Medium</option>
            <option value="high">High</option>
            <option value="urgent">Urgent</option>
          </select>
        </div>
      </div>

      {/* Tickets List */}
      <div className="flex-1 overflow-y-auto divide-y divide-slate-50">
        {isLoading ? (
          <div className="p-8 flex flex-col items-center justify-center text-slate-400">
            <div className="w-5 h-5 border-2 border-indigo-600 border-t-transparent rounded-full animate-spin mb-2" />
            <span className="text-[11px] font-medium">Loading queue...</span>
          </div>
        ) : tickets.length === 0 ? (
          <div className="p-8 text-center text-slate-400 text-xs">
            No tickets found.
          </div>
        ) : (
          tickets.map((t) => {
            const isSelected = t.id === selectedId;
            return (
              <button
                key={t.id}
                onClick={() => onSelect(t.id)}
                className={`w-full p-4 text-left transition-all flex flex-col gap-2 hover:bg-slate-50/50 cursor-pointer
                  ${isSelected ? 'bg-indigo-50/40 border-l-4 border-indigo-600' : 'border-l-4 border-transparent'}`}
              >
                <div className="flex items-start justify-between gap-2">
                  <span className="font-semibold text-slate-800 text-xs leading-tight line-clamp-1 flex-1">
                    {t.title}
                  </span>
                  <span className="text-[9px] font-mono text-slate-400">
                    {new Date(t.created_at).toLocaleDateString([], { month: 'short', day: 'numeric' })}
                  </span>
                </div>

                <p className="text-[11px] text-slate-500 line-clamp-2 leading-relaxed">
                  {t.description}
                </p>

                <div className="flex items-center justify-between mt-1">
                  <span className="text-[10px] text-slate-500 font-medium line-clamp-1 max-w-[120px]">
                    {t.customer_name || 'N/A'}
                  </span>
                  <div className="flex items-center gap-1.5">
                    <span className={`px-1.5 py-0.5 rounded text-[9px] font-semibold border ${getPriorityClass(t.priority)}`}>
                      {t.priority}
                    </span>
                    <span className="flex items-center gap-1">
                      {getStatusIcon(t.status)}
                    </span>
                  </div>
                </div>
              </button>
            );
          })
        )}
      </div>
    </div>
  );
}
