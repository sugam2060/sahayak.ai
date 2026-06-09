'use client';

import dynamic from 'next/dynamic';
import { Suspense } from 'react';
import { Loader } from '@/components/ui/Loader';
import { useAuthStore } from '@/store/authStore';

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

const DashboardWelcome = dynamic(
  () => import('@/components/dashboard').then(mod => mod.DashboardWelcome),
  {
    ssr: false,
    loading: () => (
      <div className="flex-1 flex items-center justify-center min-h-[400px]">
        <Loader size="lg" text="Loading workspace" />
      </div>
    )
  }
);

export default function Home() {
  const { user } = useAuthStore();
  const role = user?.role?.toUpperCase();
  const permissions = user?.permissions || [];

  const hasAnalytics = role === 'OWNER' || permissions.includes('analytics');

  return (
    <div className="flex-1">
      <Suspense fallback={null}>
        {hasAnalytics ? <SalesDashboard /> : <DashboardWelcome />}
      </Suspense>
    </div>
  );
}


