'use client';

import { useEffect } from 'react';
import { useAuthStore } from '@/store/authStore';
import { usePresenceStore } from '@/store/presenceStore';
import { 
  User, 
  LogOut, 
  Settings,
  Settings2
} from 'lucide-react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import Image from 'next/image';

import { logoutUser, getProfile } from '@/services/api/auth';

export const Header = () => {
  const user = useAuthStore((state) => state.user);
  const clearAuth = useAuthStore((state) => state.clearAuth);
  const updateUser = useAuthStore((state) => state.updateUser);
  const { myStatus, changeMyStatus } = usePresenceStore();
  const router = useRouter();

  useEffect(() => {
    const currentUser = useAuthStore.getState().user;
    if (!currentUser) return;

    const syncProfile = async () => {
      try {
        const profile = await getProfile();
        if (profile.success && profile.user) {
          const latestUser = useAuthStore.getState().user;
          const currentPermsStr = JSON.stringify(latestUser?.permissions || []);
          const newPermsStr = JSON.stringify(profile.user.permissions || []);
          const roleChanged = latestUser?.role !== profile.user.role;

          if (roleChanged || currentPermsStr !== newPermsStr) {
            updateUser(profile.user);
          }
        }
      } catch (err) {
        console.error("Failed to sync user profile:", err);
        clearAuth();
        router.push('/login');
      }
    };

    syncProfile();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleLogout = async () => {
    try {
      // 1. Call global logout API (clears backend session and removes cookies)
      await logoutUser();
    } catch (error) {
      console.error("Logout API failed, continuing with client-side cleanup:", error);
    } finally {
      // 2. Always clear local state and redirect
      clearAuth();
      router.push('/login');
    }
  };

  return (
    <header className="sticky top-0 z-40 w-full border-b border-zinc-200 dark:border-zinc-800 bg-white/80 dark:bg-black/80 backdrop-blur-md">
      <div className="w-full px-6 h-16 flex items-center justify-between">
        <div className="flex items-center gap-8">
          <Link href="/" className="flex items-center gap-2">
            <Image 
              src="/logo.png" 
              alt="Sahayak AI" 
              width={80} 
              height={80} 
              priority
              className="rounded-lg"
            />
          </Link>
        </div>

        <div className="flex items-center gap-3">
          <div className="flex items-center gap-3 pl-1">
            <div className="hidden lg:flex flex-col items-end mr-1">
              <span className="text-sm font-semibold text-zinc-900 dark:text-zinc-100 line-clamp-1">
                {user?.full_name || 'User'}
              </span>
              <span className="text-xs text-zinc-500 line-clamp-1">
                {user?.organization_name || 'Sahayak User'}
              </span>
            </div>
            
            <div className="relative group">
              <div className="relative cursor-pointer">
                <div className="w-10 h-10 rounded-xl bg-zinc-100 dark:bg-zinc-800 border border-zinc-200 dark:border-zinc-700 flex items-center justify-center text-primary group-hover:border-primary transition-all overflow-hidden">
                  <User size={20} />
                </div>
                <span className={`absolute -bottom-1.5 -right-1.5 w-3 h-3 rounded-full border-2 border-white dark:border-zinc-900 z-10 ${
                  myStatus === 'online' ? 'bg-emerald-500' : myStatus === 'away' ? 'bg-amber-500' : 'bg-red-600'
                }`} />
              </div>

              {/* Dropdown Menu */}
              <div className="absolute right-0 top-full pt-2 opacity-0 invisible group-hover:opacity-100 group-hover:visible transition-all duration-200 translate-y-1 group-hover:translate-y-0 z-50">
                <div className="w-56 bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-2xl shadow-xl p-2 space-y-1">
                  <div className="px-3 py-2 border-b border-zinc-100 dark:border-zinc-800 mb-1 lg:hidden">
                    <p className="text-sm font-bold truncate">{user?.full_name}</p>
                    <p className="text-xs text-zinc-500 truncate">{user?.organization_name}</p>
                  </div>
                  {/* Status Options */}
                  <div className="px-3 py-1.5 border-b border-zinc-100 dark:border-zinc-800 mb-1">
                    <span className="text-[10px] font-bold text-zinc-400 dark:text-zinc-500 uppercase tracking-wider block mb-1.5">My Status</span>
                    <div className="grid grid-cols-3 gap-1">
                      {[
                        { label: 'Online', val: 'online' as const, color: 'bg-emerald-500' },
                        { label: 'Away', val: 'away' as const, color: 'bg-amber-500' },
                        { label: 'Busy', val: 'busy' as const, color: 'bg-red-600' }
                      ].map((item) => (
                        <button
                          key={item.val}
                          onClick={() => changeMyStatus(item.val)}
                          className={`flex flex-col items-center justify-center py-1 rounded-lg border text-[10px] font-semibold transition-all ${
                            myStatus === item.val
                              ? 'border-indigo-500 bg-indigo-50/50 dark:bg-indigo-950/20 text-indigo-600 dark:text-indigo-400'
                              : 'border-zinc-100 dark:border-zinc-850 hover:bg-zinc-50 dark:hover:bg-zinc-800/50 text-zinc-500 dark:text-zinc-400'
                          }`}
                        >
                          <span className={`w-1.5 h-1.5 rounded-full ${item.color} mb-1`} />
                          {item.label}
                        </button>
                      ))}
                    </div>
                  </div>
                  <button className="w-full flex items-center gap-2 px-3 py-2 rounded-xl text-sm text-zinc-600 dark:text-zinc-400 hover:bg-zinc-100 dark:hover:bg-zinc-800 hover:text-zinc-900 dark:hover:text-zinc-100 transition-colors">
                    <Settings size={16} />
                    Account Settings
                  </button>
                  <button className="w-full flex items-center gap-2 px-3 py-2 rounded-xl text-sm text-zinc-600 dark:text-zinc-400 hover:bg-zinc-100 dark:hover:bg-zinc-800 hover:text-zinc-900 dark:hover:text-zinc-100 transition-colors">
                    <Settings2 size={16} />
                    Org Settings
                  </button>
                  <button 
                    onClick={handleLogout}
                    className="w-full flex items-center gap-2 px-3 py-2 rounded-xl text-sm text-red-600 hover:bg-red-50 transition-colors"
                  >
                    <LogOut size={16} />
                    Sign Out
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </header>
  );
};
