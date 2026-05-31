'use client';

import React, { useState, useMemo, useEffect, useCallback, Suspense } from 'react';
import { useTickets, useTicket, TicketDetail } from '@/services/api/tickets';
import { TicketListSidebar } from '@/components/ticket/TicketListSidebar';
import { TicketDetailView } from '@/components/ticket/TicketDetailView';
import { useSearchParams, useRouter, usePathname } from 'next/navigation';
import { debounce } from 'lodash';

function TicketManagementContent() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();

  const selectedId = searchParams.get('id');

  const [searchInput, setSearchInput] = useState('');
  const [debouncedSearch, setDebouncedSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [priorityFilter, setPriorityFilter] = useState<string>('all');

  const handleSelectId = useCallback((id: string | null) => {
    const params = new URLSearchParams(searchParams.toString());
    if (id) {
      params.set('id', id);
    } else {
      params.delete('id');
    }
    router.push(`${pathname}?${params.toString()}`);
  }, [searchParams, pathname, router]);

  const debouncedSearchFn = useMemo(
    () =>
      debounce((val: string) => {
        setDebouncedSearch(val);
      }, 400),
    []
  );

  const handleSearchChange = (val: string) => {
    setSearchInput(val);
    debouncedSearchFn(val);
    handleSelectId(null);
  };

  const handleStatusChange = (status: string) => {
    setStatusFilter(status);
    handleSelectId(null);
  };

  const handlePriorityChange = (priority: string) => {
    setPriorityFilter(priority);
    handleSelectId(null);
  };

  useEffect(() => {
    return () => {
      debouncedSearchFn.cancel();
    };
  }, [debouncedSearchFn]);

  const queryParams = useMemo(() => {
    return {
      limit: 50,
      search: debouncedSearch || undefined,
      status: statusFilter === 'all' ? undefined : statusFilter,
      priority: priorityFilter === 'all' ? undefined : priorityFilter,
    };
  }, [debouncedSearch, statusFilter, priorityFilter]);

  const { data, isLoading } = useTickets(queryParams);
  const tickets: TicketDetail[] = useMemo(() => data?.tickets || [], [data?.tickets]);

  useEffect(() => {
    if (!selectedId && tickets.length > 0) {
      handleSelectId(tickets[0].id);
    }
  }, [tickets, selectedId, handleSelectId]);

  const { data: selectedTicket, isLoading: isDetailLoading } = useTicket(selectedId || '');

  return (
    <div className="flex h-[calc(100vh-64px)] overflow-hidden bg-white/20">
      <TicketListSidebar
        tickets={tickets}
        selectedId={selectedId}
        onSelect={handleSelectId}
        searchTerm={searchInput}
        onSearchChange={handleSearchChange}
        statusFilter={statusFilter}
        onStatusChange={handleStatusChange}
        priorityFilter={priorityFilter}
        onPriorityChange={handlePriorityChange}
        isLoading={isLoading}
      />

      <TicketDetailView
        ticket={selectedTicket || null}
        isLoading={isDetailLoading && !!selectedId}
      />
    </div>
  );
}

export default function TicketManagementPage() {
  return (
    <Suspense fallback={
      <div className="flex h-[calc(100vh-64px)] items-center justify-center bg-white/20 text-slate-500">
        <div className="w-8 h-8 border-2 border-primary border-t-transparent rounded-full animate-spin mb-4" />
        <span className="text-sm font-medium">Loading workspace...</span>
      </div>
    }>
      <TicketManagementContent />
    </Suspense>
  );
}
