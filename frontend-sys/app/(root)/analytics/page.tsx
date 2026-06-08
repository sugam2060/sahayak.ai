'use client';

import dynamic from 'next/dynamic';
import { Suspense } from 'react';
import { Loader } from '@/components/ui/Loader';

const AnalyticsHub = dynamic(
  () => import('@/components/analytics/AnalyticsHub').then(mod => mod.AnalyticsHub),
  {
    ssr: false,
    loading: () => (
      <div className="flex-1 flex items-center justify-center min-h-[500px]">
        <Loader size="lg" text="Loading Analytics" />
      </div>
    ),
  }
);

export default function AnalyticsPage() {
  return (
    <div className="flex-1">
      <Suspense fallback={null}>
        <AnalyticsHub />
      </Suspense>
    </div>
  );
}
