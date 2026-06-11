import { create } from 'zustand';
import { persist } from 'zustand/middleware';

interface UnreadState {
  unreadCounts: Record<string, number>;
  activeKey: string | null;
  isDialogOpen: boolean;
  increment: (key: string) => void;
  clear: (key: string) => void;
  setActiveKey: (key: string | null) => void;
  setIsDialogOpen: (open: boolean) => void;
  getTotalUnread: () => number;
}

export const useUnreadStore = create<UnreadState>()(
  persist(
    (set, get) => ({
      unreadCounts: {},
      activeKey: null,
      isDialogOpen: false,
      increment: (key) => {
        const state = get();
        // Only increment if we are not actively looking at this conversation
        if (state.isDialogOpen && state.activeKey === key) {
          return;
        }
        set((state) => ({
          unreadCounts: {
            ...state.unreadCounts,
            [key]: (state.unreadCounts[key] || 0) + 1,
          },
        }));
      },
      clear: (key) => {
        set((state) => {
          const newCounts = { ...state.unreadCounts };
          delete newCounts[key];
          return { unreadCounts: newCounts };
        });
      },
      setActiveKey: (key) => {
        set({ activeKey: key });
        // Auto-clear when setting active key
        if (key) {
          get().clear(key);
        }
      },
      setIsDialogOpen: (open) => {
        set({ isDialogOpen: open });
        // Auto-clear active key when opening dialog if activeKey is set
        const activeKey = get().activeKey;
        if (open && activeKey) {
          get().clear(activeKey);
        }
      },
      getTotalUnread: () => {
        return Object.values(get().unreadCounts).reduce((a, b) => a + b, 0);
      },
    }),
    {
      name: 'sahayak-internal-unread-storage',
      partialize: (state) => ({ unreadCounts: state.unreadCounts }), // only persist unreadCounts
    }
  )
);
