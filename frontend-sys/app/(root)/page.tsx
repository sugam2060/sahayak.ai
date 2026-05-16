'use client';

import dynamic from 'next/dynamic';
import { Suspense } from 'react';
import { Loader } from '@/components/ui/Loader';

// Dynamically import the dashboard with SSR disabled
const SalesDashboard = dynamic(
  () => import('@/components/dashboard').then(mod => mod.SalesDashboard),
  { 
    ssr: false,
    loading: () => (
      <div className="flex-1 flex items-center justify-center min-h-[400px]">
        <Loader size="lg" text="Initializing Dashboard" />
      </div>
    )
  }
);

export default function Home() {
  return (
    <div className="flex-1">
      <Suspense fallback={null}>
        <SalesDashboard />
      </Suspense>
    </div>
  );
}
