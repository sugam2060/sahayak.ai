'use client';

import { RiUser3Line, RiLockPasswordLine, RiMailLine, RiLoader4Line, RiAlertLine } from 'react-icons/ri';

import { useAccountProfile } from '@/services/api/account';
import { ProfileTab } from './ProfileTab';
import { PasswordTab } from './PasswordTab';
import { EmailTab } from './EmailTab';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';

interface AccountSettingsModalProps {
  open: boolean;
  onClose: () => void;
}

export const AccountSettingsModal = ({ open, onClose }: AccountSettingsModalProps) => {
  const { data: profile, isLoading, isError, error } = useAccountProfile();

  return (
    <Dialog open={open} onOpenChange={(v) => !v && onClose()}>
      <DialogContent className="sm:max-w-lg bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-2xl p-0 overflow-hidden shadow-2xl">
        {/* Header */}
        <DialogHeader className="px-6 pt-6 pb-4 border-b border-zinc-100 dark:border-zinc-800">
          <DialogTitle className="text-xl font-bold text-zinc-900 dark:text-white flex items-center gap-2">
            <span className="w-8 h-8 rounded-lg bg-gradient-to-br from-indigo-500 to-violet-600 flex items-center justify-center">
              <RiUser3Line size={16} className="text-white" />
            </span>
            Account Settings
          </DialogTitle>
          <DialogDescription className="text-xs text-zinc-500 dark:text-zinc-400 mt-1">
            Manage your personal profile, security, and email preferences.
          </DialogDescription>
        </DialogHeader>

        {/* Body */}
        <div className="px-6 pb-6 pt-4">
          {isLoading && (
            <div className="flex flex-col items-center justify-center py-12 gap-3 text-zinc-400">
              <RiLoader4Line size={32} className="animate-spin" />
              <p className="text-xs">Loading your profile…</p>
            </div>
          )}

          {isError && (
            <div className="flex flex-col items-center justify-center py-10 gap-3 text-center">
              <div className="w-12 h-12 rounded-full bg-red-50 dark:bg-red-950/20 flex items-center justify-center text-red-500">
                <RiAlertLine size={22} />
              </div>
              <div>
                <p className="text-sm font-semibold text-zinc-900 dark:text-white">
                  Could not load profile
                </p>
                <p className="text-xs text-zinc-500 dark:text-zinc-400 mt-0.5 max-w-xs">
                  {(error as Error)?.message || 'An unexpected error occurred.'}
                </p>
              </div>
            </div>
          )}

          {!isLoading && !isError && profile && (
            <Tabs defaultValue="profile" className="w-full">
              <TabsList className="w-full grid grid-cols-3 mb-6 bg-zinc-100 dark:bg-zinc-800 rounded-xl p-1 h-auto">
                <TabsTrigger
                  value="profile"
                  className="rounded-lg text-xs font-semibold py-2 flex items-center justify-center gap-1.5 data-[state=active]:bg-white dark:data-[state=active]:bg-zinc-700 data-[state=active]:shadow-sm transition-all"
                >
                  <RiUser3Line size={14} />
                  Profile
                </TabsTrigger>
                <TabsTrigger
                  value="password"
                  className="rounded-lg text-xs font-semibold py-2 flex items-center justify-center gap-1.5 data-[state=active]:bg-white dark:data-[state=active]:bg-zinc-700 data-[state=active]:shadow-sm transition-all"
                >
                  <RiLockPasswordLine size={14} />
                  Password
                </TabsTrigger>
                <TabsTrigger
                  value="email"
                  className="rounded-lg text-xs font-semibold py-2 flex items-center justify-center gap-1.5 data-[state=active]:bg-white dark:data-[state=active]:bg-zinc-700 data-[state=active]:shadow-sm transition-all"
                >
                  <RiMailLine size={14} />
                  Email
                </TabsTrigger>
              </TabsList>

              <TabsContent value="profile" className="mt-0 animate-in fade-in slide-in-from-bottom-2 duration-200">
                <ProfileTab profile={profile} />
              </TabsContent>

              <TabsContent value="password" className="mt-0 animate-in fade-in slide-in-from-bottom-2 duration-200">
                <PasswordTab />
              </TabsContent>

              <TabsContent value="email" className="mt-0 animate-in fade-in slide-in-from-bottom-2 duration-200">
                <EmailTab profile={profile} />
              </TabsContent>
            </Tabs>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
};
