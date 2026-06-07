import { create } from 'zustand';
import { persist, createJSONStorage } from 'zustand/middleware';
import { LoginResponse } from '@/types/auth';

interface AuthState {
  user: Partial<LoginResponse> | null;
  isAuthenticated: boolean;
  setAuth: (data: LoginResponse) => void;
  clearAuth: () => void;
  updateUser: (data: Partial<LoginResponse>) => void;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      user: null,
      isAuthenticated: false,
      setAuth: (data) => set({ 
        user: {
          user_id: data.user_id,
          organization_id: data.organization_id,
          full_name: data.full_name,
          organization_name: data.organization_name,
          organization_slug: data.organization_slug,
          email: data.email,
          is_verified: data.is_verified,
          role: data.role,
          permissions: data.permissions || [],
        }, 
        isAuthenticated: true 
      }),
      clearAuth: () => set({ user: null, isAuthenticated: false }),
      updateUser: (data) => set((state) => ({
        user: state.user ? { ...state.user, ...data } : null
      })),
    }),
    {
      name: 'sahayak-auth',
      storage: createJSONStorage(() => localStorage),
    }
  )
);
