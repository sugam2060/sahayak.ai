'use client';

import React, { useState, useMemo, useEffect, Suspense } from 'react';
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

  const handleSelectId = (id: string | null) => {
    const params = new URLSearchParams(searchParams.toString());
    if (id) {
      params.set('id', id);
    } else {
      params.delete('id');
    }
    router.push(`${pathname}?${params.toString()}`);
  };

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
  };

  useEffect(() => {
    return () => {
      debouncedSearchFn.cancel();
    };
  }, [debouncedSearchFn]);

  useEffect(() => {
    handleSelectId(null);
  }, [debouncedSearch, statusFilter, priorityFilter]);

  const queryParams = useMemo(() => {
    return {
      limit: 50,
      search: debouncedSearch || undefined,
      status: statusFilter === 'all' ? undefined : statusFilter,
      priority: priorityFilter === 'all' ? undefined : priorityFilter,
    };
  }, [debouncedSearch, statusFilter, priorityFilter]);

  const { data, isLoading } = useTickets(queryParams);
  const tickets: TicketDetail[] = data?.tickets || [];

  useEffect(() => {
    if (!selectedId && tickets.length > 0) {
      handleSelectId(tickets[0].id);
    }
  }, [tickets, selectedId]);

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
        onStatusChange={setStatusFilter}
        priorityFilter={priorityFilter}
        onPriorityChange={setPriorityFilter}
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
