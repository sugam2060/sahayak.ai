'use client';

import { useEffect } from 'react';
import { useAuthStore } from '@/store/authStore';
import { usePresenceStore } from '@/store/presenceStore';

export function PresenceObserver() {
  const { user, isAuthenticated } = useAuthStore();
  const { connectPresence, disconnectPresence } = usePresenceStore();

  useEffect(() => {
    if (isAuthenticated && user?.organization_id && user?.user_id) {
      connectPresence(user.organization_id, user.user_id);
    } else {
      disconnectPresence();
    }

    return () => {
      disconnectPresence();
    };
  }, [isAuthenticated, user?.organization_id, user?.user_id, connectPresence, disconnectPresence]);

  return null;
}
