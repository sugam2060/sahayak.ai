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
import { Settings2 } from 'lucide-react';

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
import * as VisuallyHidden from '@radix-ui/react-visually-hidden';

// ─── Schema ──────────────────────────────────────────────────────────────────

const orgFormSchema = z.object({
    name: z.string().min(2, 'Organization name must be at least 2 characters').max(255),
    slug: z.string().min(2, 'Slug must be at least 2 characters').max(100),
});

type OrgFormValues = z.infer<typeof orgFormSchema>;

// ─── Inner content (same layout as the original page) ────────────────────────

function OrgSettingsContent({ onClose }: { onClose: () => void }) {
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
        defaultValues: { name: '', slug: '' },
    });

    useEffect(() => {
        if (org) reset({ name: org.name, slug: org.slug });
    }, [org, reset]);

    const onSave = async (values: OrgFormValues) => {
        try {
            await updateMutation.mutateAsync({ name: values.name, slug: values.slug });
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
            try {
                await logoutUser();
            } catch (logoutErr) {
                console.warn('Backend logout failed, proceeding with client cleanup', logoutErr);
            } finally {
                setIsDeactivateOpen(false);
                onClose();
                clearAuth();
                router.push('/login');
            }
        } catch (err) {
            const error = err as Error;
            toast.error(error.message || 'Failed to deactivate organization.');
        }
    };

    // ── Loading ──
    if (isLoading) {
        return (
            <div className="flex h-64 items-center justify-center">
                <Loader size="lg" text="Retrieving Organization Workspace..." />
            </div>
        );
    }

    // ── Error ──
    if (error) {
        return (
            <div className="p-8 text-center space-y-4">
                <div className="inline-flex items-center justify-center p-4 bg-red-50 dark:bg-red-950/20 text-red-500 rounded-2xl">
                    <RiAlertLine size={32} />
                </div>
                <h2 className="text-xl font-bold text-zinc-900 dark:text-white">Error Loading Organization</h2>
                <p className="text-zinc-500 dark:text-zinc-400 max-w-md mx-auto">
                    {error.message || 'An unknown error occurred.'}
                </p>
            </div>
        );
    }

    return (
        <>
            {/* ── Dialog Header ── */}
            <DialogHeader className="border-b border-zinc-150 dark:border-zinc-800 pb-5">
                <DialogTitle className="text-xl font-bold text-zinc-900 dark:text-white flex items-center gap-2">
                    <RiSettings4Line className="text-primary" />
                    Organization Settings
                </DialogTitle>
                <DialogDescription className="text-zinc-500 dark:text-zinc-400 text-sm mt-1">
                    Manage your organization profile, configure unique identifier tags, and manage active status.
                </DialogDescription>
            </DialogHeader>

            {/* ── Body ── */}
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 pt-2">

                {/* Left: Org Overview */}
                <div className="lg:col-span-1">
                    <div className="bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-2xl p-5 shadow-sm space-y-4 h-full">
                        <h2 className="text-base font-semibold text-zinc-900 dark:text-white border-b border-zinc-150 dark:border-zinc-800 pb-3 flex items-center gap-2">
                            <RiInformationLine size={16} className="text-zinc-400" />
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
                                    {org?.created_at
                                        ? new Date(org.created_at).toLocaleDateString(undefined, { dateStyle: 'long' })
                                        : '-'}
                                </span>
                            </div>

                            <div>
                                <span className="text-[10px] font-bold text-zinc-400 uppercase tracking-wider block">Last Updated</span>
                                <span className="text-xs text-zinc-700 dark:text-zinc-300 block mt-1">
                                    {org?.updated_at
                                        ? new Date(org.updated_at).toLocaleDateString(undefined, { dateStyle: 'long' })
                                        : '-'}
                                </span>
                            </div>
                        </div>
                    </div>
                </div>

                {/* Right: Form + Danger Zone */}
                <div className="lg:col-span-2 space-y-6">

                    {/* Main Settings Form */}
                    <div className="bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-2xl p-5 shadow-sm">
                        <h2 className="text-base font-semibold text-zinc-900 dark:text-white border-b border-zinc-150 dark:border-zinc-800 pb-3 mb-5">
                            Organization Info
                        </h2>

                        <form onSubmit={handleSubmit(onSave)} className="space-y-5">
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
                                <Input
                                    id="slug"
                                    type="text"
                                    placeholder="e.g. acme-corp"
                                    className="bg-zinc-50 dark:bg-zinc-800 border-zinc-200 dark:border-zinc-700"
                                    {...register('slug')}
                                />
                                <span className="text-[11px] text-zinc-500 dark:text-zinc-400 block">
                                    The slug is a unique, URL-friendly identifier. E.g. sahayak.sugampudasain.xyz/orgs/{'{slug}'}
                                </span>
                                {errors.slug && (
                                    <p className="text-xs text-red-500 font-sans mt-1">{errors.slug.message}</p>
                                )}
                            </div>

                            <div className="flex justify-end pt-1">
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
                    <div className="bg-red-50/20 dark:bg-red-950/10 border border-red-200/50 dark:border-red-900/30 rounded-2xl p-5 space-y-3">
                        <h2 className="text-base font-bold text-red-700 dark:text-red-400 flex items-center gap-2">
                            <RiAlertLine size={18} />
                            Danger Zone
                        </h2>
                        <p className="text-xs text-zinc-650 dark:text-zinc-400 leading-relaxed">
                            Deactivating this organization will immediately sign out all users, lock all accounts, and disable API
                            features. This action is reversible by an administrator but disrupts services immediately.
                        </p>
                        <div className="pt-1">
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

            {/* ── Nested Deactivation Confirmation Dialog ── */}
            <Dialog open={isDeactivateOpen} onOpenChange={setIsDeactivateOpen}>
                <DialogContent className="sm:max-w-md bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-2xl p-6">
                    <DialogHeader>
                        <DialogTitle className="text-xl font-bold font-heading text-zinc-900 dark:text-white flex items-center gap-2">
                            <RiShieldKeyholeLine className="text-red-500" />
                            Confirm Deactivation
                        </DialogTitle>
                        <DialogDescription className="text-xs text-zinc-500 dark:text-zinc-400 mt-2 leading-relaxed">
                            This action deactivates the organization profile. Active session tokens in Redis will be invalidated and
                            all active users will be immediately logged out.
                        </DialogDescription>
                    </DialogHeader>

                    <div className="space-y-4 py-4 border-t border-b border-zinc-100 dark:border-zinc-800 my-2">
                        <p className="text-xs text-zinc-700 dark:text-zinc-300">
                            To proceed, please type your organization name exactly as shown below:
                            <strong className="block text-sm font-bold text-zinc-900 dark:text-white mt-1 select-all">
                                {org?.name}
                            </strong>
                        </p>
                        <Input
                            type="text"
                            value={confirmNameInput}
                            onChange={(e) => setConfirmNameInput(e.target.value)}
                            placeholder="Type organization name to verify"
                            className="w-full bg-zinc-50 dark:bg-zinc-800 border-zinc-200 dark:border-zinc-700"
                        />
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
        </>
    );
}

// ─── Main export: the trigger button + outer dialog ──────────────────────────

export function OrgSettingsDialog() {
    const [open, setOpen] = useState(false);

    return (
        <>
            {/* Sidebar trigger button — drop-in replacement for the original */}
            <button
                onClick={() => setOpen(true)}
                className="w-full flex items-center gap-2 px-3 py-2 rounded-xl text-sm text-zinc-600 dark:text-zinc-400 hover:bg-zinc-100 dark:hover:bg-zinc-800 hover:text-zinc-900 dark:hover:text-zinc-100 transition-colors"
            >
                <Settings2 size={16} />
                Org Settings
            </button>

            {/* Outer settings dialog */}
            <Dialog open={open} onOpenChange={setOpen}>
                <DialogContent
                    className="
            bg-white dark:bg-zinc-950
            border border-zinc-200 dark:border-zinc-800
            rounded-2xl
            p-6 md:p-8
            overflow-y-auto
            max-h-[90vh]
          "
                    style={{ width: '90vw', maxWidth: '1100px' }}
                >
                    {/* Satisfies Radix accessibility requirement — visually hidden, real title is inside OrgSettingsContent */}
                    <VisuallyHidden.Root>
                        <DialogTitle>Organization Settings</DialogTitle>
                    </VisuallyHidden.Root>

                    <OrgSettingsContent onClose={() => setOpen(false)} />
                </DialogContent>
            </Dialog>
        </>
    );
}

// Keep page export for backward compatibility if needed
export default function OrgSettingsPage() {
    return <OrgSettingsDialog />;
}