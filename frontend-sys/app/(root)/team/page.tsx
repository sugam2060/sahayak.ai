'use client';

import dynamic from 'next/dynamic';
import { Suspense } from 'react';
import { Loader } from '@/components/ui/Loader';

const TeamList = dynamic(
  () => import('@/components/team/TeamList').then(mod => mod.TeamList),
  { 
    ssr: false,
    loading: () => (
      <div className="flex-1 flex items-center justify-center min-h-[400px]">
        <Loader size="lg" text="Initializing Teams Workspace..." />
      </div>
    )
  }
);

export default function TeamsPage() {
  return (
    <div className="flex-1">
      <Suspense fallback={null}>
        <TeamList />
      </Suspense>
    </div>
  );
}
