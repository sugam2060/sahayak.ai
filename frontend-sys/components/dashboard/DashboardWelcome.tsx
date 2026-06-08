'use client';

import { MessageSquare, Ticket, Users, ArrowRight, Sparkles } from 'lucide-react';
import Link from 'next/link';
import { useAuthStore } from '@/store/authStore';

const quickActions = [
  {
    title: 'Inbox',
    description: 'View and respond to customer conversations',
    icon: MessageSquare,
    href: '/inbox',
    permission: 'chats',
    gradient: 'from-blue-500 to-cyan-500',
    bgGlow: 'bg-blue-500/10',
  },
  {
    title: 'Support Tickets',
    description: 'Track and resolve open support requests',
    icon: Ticket,
    href: '/ticket',
    permission: 'tickets',
    gradient: 'from-purple-500 to-pink-500',
    bgGlow: 'bg-purple-500/10',
  },
  {
    title: 'Team Settings',
    description: 'Manage your team roles and permissions',
    icon: Users,
    href: '/team',
    permission: 'teams',
    gradient: 'from-amber-500 to-orange-500',
    bgGlow: 'bg-amber-500/10',
  },
];

export const DashboardWelcome = () => {
  const { user } = useAuthStore();
  const userRole = user?.role?.toUpperCase();
  const permissions = user?.permissions || [];

  const visibleActions = quickActions.filter(action => {
    if (userRole === 'OWNER') return true;
    return permissions.includes(action.permission);
  });

  const firstName = user?.full_name?.split(' ')[0] || 'there';

  return (
    <div className="space-y-8 animate-in fade-in slide-in-from-bottom-4 duration-500 max-w-[900px] mx-auto p-6">
      {/* Welcome Banner */}
      <div className="relative overflow-hidden rounded-2xl bg-gradient-to-br from-primary/10 via-purple-500/5 to-pink-500/5 border border-primary/10 p-8">
        <div className="absolute top-4 right-4 opacity-20">
          <Sparkles size={80} className="text-primary" />
        </div>
        <div className="relative z-10">
          <h1 className="text-3xl font-bold text-zinc-900 dark:text-white font-heading">
            Welcome back, {firstName}! 👋
          </h1>
          <p className="mt-2 text-sm text-zinc-600 dark:text-zinc-400 max-w-md">
            Here&apos;s your workspace hub. Jump into your conversations, resolve tickets, or manage your team.
          </p>
        </div>
        {/* Decorative gradient blobs */}
        <div className="absolute -bottom-12 -left-12 w-40 h-40 bg-primary/10 rounded-full blur-3xl" />
        <div className="absolute -top-8 -right-8 w-32 h-32 bg-purple-500/10 rounded-full blur-3xl" />
      </div>

      {/* Quick Actions */}
      {visibleActions.length > 0 && (
        <div>
          <h2 className="text-sm font-bold text-zinc-500 dark:text-zinc-400 uppercase tracking-wider mb-4">
            Quick Actions
          </h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {visibleActions.map((action) => (
              <Link
                key={action.title}
                href={action.href}
                className="group relative bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-2xl p-5 hover:shadow-lg hover:shadow-primary/5 transition-all duration-300 hover:-translate-y-0.5"
              >
                <div className={`absolute inset-0 rounded-2xl ${action.bgGlow} opacity-0 group-hover:opacity-100 transition-opacity duration-300`} />
                <div className="relative z-10">
                  <div className={`w-10 h-10 rounded-xl bg-gradient-to-br ${action.gradient} flex items-center justify-center text-white mb-4 shadow-sm`}>
                    <action.icon size={18} />
                  </div>
                  <h3 className="text-sm font-bold text-zinc-900 dark:text-white group-hover:text-primary transition-colors">
                    {action.title}
                  </h3>
                  <p className="text-xs text-zinc-500 dark:text-zinc-400 mt-1 leading-relaxed">
                    {action.description}
                  </p>
                  <div className="flex items-center gap-1 mt-3 text-xs font-bold text-primary opacity-0 group-hover:opacity-100 transition-all duration-300 translate-x-0 group-hover:translate-x-1">
                    <span>Open</span>
                    <ArrowRight size={12} />
                  </div>
                </div>
              </Link>
            ))}
          </div>
        </div>
      )}

      {/* Workspace Info */}
      <div className="bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-2xl p-6">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 bg-zinc-100 dark:bg-zinc-800 rounded-xl flex items-center justify-center">
            <Sparkles size={18} className="text-zinc-400" />
          </div>
          <div>
            <h3 className="text-sm font-bold text-zinc-900 dark:text-white">
              {user?.organization_name || 'Your Organization'}
            </h3>
            <p className="text-xs text-zinc-500 dark:text-zinc-400">
              Role: <span className="font-semibold text-zinc-700 dark:text-zinc-300">{user?.role || 'Member'}</span>
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};
