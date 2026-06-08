'use client';

import React, { useState, useEffect } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import * as z from 'zod';
import { toast } from 'sonner';
import { useRouter } from 'next/navigation';
import {
  RiSettings4Line,
  RiCheckDoubleLine,
  RiAlertLine,
  RiDeleteBin2Line,
  RiShieldKeyholeLine,
  RiInformationLine
} from 'react-icons/ri';

import { useAuthStore } from '@/store/authStore';
import { logoutUser } from '@/services/api/auth';
import {
  useOrganization,
  useUpdateOrganization,
  useDeleteOrganization
} from '@/services/api/organizations';

import { Loader } from '@/components/ui/Loader';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogFooter
} from '@/components/ui/dialog';

const orgFormSchema = z.object({
  name: z.string().min(2, 'Organization name must be at least 2 characters').max(255),
  slug: z.string().min(2, 'Slug must be at least 2 characters').max(100),
});

type OrgFormValues = z.infer<typeof orgFormSchema>;

export default function OrgSettingsPage() {
  const router = useRouter();
  const clearAuth = useAuthStore((state) => state.clearAuth);

  const { data: org, isLoading, error } = useOrganization();
  const updateMutation = useUpdateOrganization();
  const deleteMutation = useDeleteOrganization();

  const [isDeactivateOpen, setIsDeactivateOpen] = useState(false);
  const [confirmNameInput, setConfirmNameInput] = useState('');

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<OrgFormValues>({
    resolver: zodResolver(orgFormSchema),
    defaultValues: {
      name: '',
      slug: '',
    },
  });

  // Populate form defaults once org data is retrieved
  useEffect(() => {
    if (org) {
      reset({
        name: org.name,
        slug: org.slug,
      });
    }
  }, [org, reset]);

  const onSave = async (values: OrgFormValues) => {
    try {
      await updateMutation.mutateAsync({
        name: values.name,
        slug: values.slug,
      });
      toast.success('Organization settings updated successfully.');
    } catch (err) {
      const error = err as Error;
      toast.error(error.message || 'Failed to update organization settings.');
    }
  };

  const handleDeactivate = async () => {
    if (!org) return;
    if (confirmNameInput !== org.name) {
      toast.error('The organization name you typed did not match. Deactivation aborted.');
      return;
    }

    try {
      await deleteMutation.mutateAsync();
      toast.success('Organization deactivated. Logging out...');

      // Clear sessions and redirect
      try {
        await logoutUser();
      } catch (logoutErr) {
        console.warn('Backend logout failed, proceeding with client cleanup', logoutErr);
      } finally {
        setIsDeactivateOpen(false);
        clearAuth();
        router.push('/login');
      }
    } catch (err) {
      const error = err as Error;
      toast.error(error.message || 'Failed to deactivate organization.');
    }
  };

  if (isLoading) {
    return (
      <div className="flex h-[80vh] items-center justify-center">
        <Loader size="lg" text="Retrieving Organization Workspace..." />
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-8 max-w-4xl mx-auto text-center space-y-4">
        <div className="inline-flex items-center justify-center p-4 bg-red-50 dark:bg-red-950/20 text-red-500 rounded-2xl">
          <RiAlertLine size={32} />
        </div>
        <h2 className="text-xl font-bold text-zinc-900 dark:text-white">Error Loading Organization</h2>
        <p className="text-zinc-500 dark:text-zinc-400 max-w-md mx-auto">{error.message || 'An unknown error occurred.'}</p>
      </div>
    );
  }

  return (
    <div className="p-6 md:p-8 max-w-5xl mx-auto space-y-8 animate-in fade-in duration-300">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-zinc-150 dark:border-zinc-800 pb-6">
        <div>
          <h1 className="text-2xl font-bold text-zinc-900 dark:text-white flex items-center gap-2">
            <RiSettings4Line className="text-primary" />
            Organization Settings
          </h1>
          <p className="text-zinc-500 dark:text-zinc-400 text-sm mt-1">
            Manage your organization profile, configure unique identifier tags, and manage active status.
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Left Card: Metadata Profile */}
        <div className="lg:col-span-1 space-y-6">
          <div className="bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-2xl p-6 shadow-sm space-y-6">
            <h2 className="text-lg font-semibold text-zinc-900 dark:text-white border-b border-zinc-150 dark:border-zinc-800 pb-3 flex items-center gap-2">
              <RiInformationLine size={18} className="text-zinc-400" />
              Org Overview
            </h2>

            <div className="space-y-4">
              <div>
                <span className="text-[10px] font-bold text-zinc-400 uppercase tracking-wider block">Plan Type</span>
                <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold mt-1 bg-indigo-50 text-indigo-700 dark:bg-indigo-950/20 dark:text-indigo-400 border border-indigo-100 dark:border-indigo-900/50 capitalize">
                  {org?.plan || 'Free'} Plan
                </span>
              </div>

              <div>
                <span className="text-[10px] font-bold text-zinc-400 uppercase tracking-wider block">Organization ID</span>
                <span className="text-xs font-mono text-zinc-600 dark:text-zinc-300 break-all select-all block mt-1">
                  {org?.id}
                </span>
              </div>

              <div>
                <span className="text-[10px] font-bold text-zinc-400 uppercase tracking-wider block">Created On</span>
                <span className="text-xs text-zinc-700 dark:text-zinc-300 block mt-1">
                  {org?.created_at ? new Date(org.created_at).toLocaleDateString(undefined, { dateStyle: 'long' }) : '-'}
                </span>
              </div>

              <div>
                <span className="text-[10px] font-bold text-zinc-400 uppercase tracking-wider block">Last Updated</span>
                <span className="text-xs text-zinc-700 dark:text-zinc-300 block mt-1">
                  {org?.updated_at ? new Date(org.updated_at).toLocaleDateString(undefined, { dateStyle: 'long' }) : '-'}
                </span>
              </div>
            </div>
          </div>
        </div>

        {/* Right Form: Settings Form & Danger Zone */}
        <div className="lg:col-span-2 space-y-8">
          {/* Main Settings Form */}
          <div className="bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-2xl p-6 shadow-sm">
            <h2 className="text-lg font-semibold text-zinc-900 dark:text-white border-b border-zinc-150 dark:border-zinc-800 pb-3 mb-6">
              Organization Info
            </h2>

            <form onSubmit={handleSubmit(onSave)} className="space-y-6">
              <div className="space-y-2">
                <Label htmlFor="name" className="text-sm font-semibold text-zinc-700 dark:text-zinc-350">
                  Organization Name
                </Label>
                <Input
                  id="name"
                  type="text"
                  placeholder="e.g. Acme Corp"
                  className="bg-zinc-50 dark:bg-zinc-800 border-zinc-200 dark:border-zinc-700"
                  {...register('name')}
                />
                {errors.name && (
                  <p className="text-xs text-red-500 font-sans mt-1">{errors.name.message}</p>
                )}
              </div>

              <div className="space-y-2">
                <Label htmlFor="slug" className="text-sm font-semibold text-zinc-700 dark:text-zinc-350">
                  Organization Slug
                </Label>
                <div className="relative flex items-center">
                  <Input
                    id="slug"
                    type="text"
                    placeholder="e.g. acme-corp"
                    className="bg-zinc-50 dark:bg-zinc-800 border-zinc-200 dark:border-zinc-700 pr-3"
                    {...register('slug')}
                  />
                </div>
                <span className="text-[11px] text-zinc-500 dark:text-zinc-400 block">
                  The slug is a unique, URL-friendly identifier. E.g. sahayak.sugampudasain.xyz/orgs/{"{slug}"}
                </span>
                {errors.slug && (
                  <p className="text-xs text-red-500 font-sans mt-1">{errors.slug.message}</p>
                )}
              </div>

              <div className="flex justify-end pt-2">
                <Button
                  type="submit"
                  disabled={updateMutation.isPending}
                  className="px-5 py-2.5 bg-primary text-white font-medium rounded-xl hover:bg-primary/95 transition-all shadow-lg shadow-primary/20 flex items-center justify-center gap-2"
                >
                  {updateMutation.isPending ? (
                    <Loader size="sm" className="text-white" />
                  ) : (
                    <RiCheckDoubleLine size={18} />
                  )}
                  Save Changes
                </Button>
              </div>
            </form>
          </div>

          {/* Danger Zone */}
          <div className="bg-red-50/20 dark:bg-red-950/10 border border-red-200/50 dark:border-red-900/30 rounded-2xl p-6 space-y-4">
            <h2 className="text-lg font-bold text-red-700 dark:text-red-400 flex items-center gap-2">
              <RiAlertLine size={20} />
              Danger Zone
            </h2>
            <p className="text-xs text-zinc-650 dark:text-zinc-400 max-w-2xl leading-relaxed">
              Deactivating this organization will immediately sign out all users, lock all accounts, and disable API features.
              This action is reversible by an administrator but disrupts services immediately.
            </p>

            <div className="pt-2">
              <Button
                variant="destructive"
                onClick={() => {
                  setConfirmNameInput('');
                  setIsDeactivateOpen(true);
                }}
                className="bg-red-600 hover:bg-red-700 text-white font-semibold rounded-xl flex items-center gap-2 cursor-pointer"
              >
                <RiDeleteBin2Line size={16} />
                Deactivate Organization
              </Button>
            </div>
          </div>
        </div>
      </div>

      {/* Confirmation Dialog */}
      <Dialog open={isDeactivateOpen} onOpenChange={setIsDeactivateOpen}>
        <DialogContent className="sm:max-w-md bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-2xl p-6">
          <DialogHeader>
            <DialogTitle className="text-xl font-bold font-heading text-zinc-900 dark:text-white flex items-center gap-2">
              <RiShieldKeyholeLine className="text-red-500" />
              Confirm Deactivation
            </DialogTitle>
            <DialogDescription className="text-xs text-zinc-500 dark:text-zinc-400 mt-2 leading-relaxed">
              This action deactivates the organization profile. Active session tokens in Redis will be invalidated and all active users will be immediately logged out.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4 py-4 border-t border-b border-zinc-100 dark:border-zinc-800 my-2">
            <p className="text-xs text-zinc-700 dark:text-zinc-300">
              To proceed, please type your organization name exactly as shown below:
              <strong className="block text-sm font-bold text-zinc-900 dark:text-white mt-1 select-all">{org?.name}</strong>
            </p>

            <div className="space-y-2">
              <Input
                type="text"
                value={confirmNameInput}
                onChange={(e) => setConfirmNameInput(e.target.value)}
                placeholder="Type organization name to verify"
                className="w-full bg-zinc-50 dark:bg-zinc-800 border-zinc-200 dark:border-zinc-700"
              />
            </div>
          </div>

          <DialogFooter className="gap-2 sm:gap-0">
            <Button
              variant="outline"
              onClick={() => setIsDeactivateOpen(false)}
              className="border-zinc-200 dark:border-zinc-800 rounded-xl"
            >
              Cancel
            </Button>
            <Button
              variant="destructive"
              onClick={handleDeactivate}
              disabled={confirmNameInput !== org?.name || deleteMutation.isPending}
              className="bg-red-600 hover:bg-red-700 text-white rounded-xl disabled:opacity-50"
            >
              {deleteMutation.isPending ? (
                <Loader size="sm" className="text-white" />
              ) : (
                'Confirm Deactivation'
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
