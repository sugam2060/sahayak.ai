'use client';

import { useEffect } from 'react';
import { useAuthStore } from '@/store/authStore';
import { useRouter } from 'next/navigation';

export function SessionObserver() {
  const logout = useAuthStore((state) => state.logout);
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);
  const router = useRouter();

  useEffect(() => {
    // This runs on the client side
    const checkSession = () => {
      // If we are on /login, we should ensure we are logged out in Store
      if (window.location.pathname === '/login' && isAuthenticated) {
        logout();
      }
    };

    checkSession();
    
    // Also handle storage events (sync between tabs)
    const handleStorageChange = (e: StorageEvent) => {
      if (e.key === 'auth-storage' && !e.newValue) {
        logout();
      }
    };

    window.addEventListener('storage', handleStorageChange);
    return () => window.removeEventListener('storage', handleStorageChange);
  }, [isAuthenticated, logout, router]);

  return null;
}
