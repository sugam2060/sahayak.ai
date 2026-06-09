'use client';

import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import * as z from 'zod';
import { toast } from 'sonner';
import { RiUser3Line, RiCheckLine, RiShieldUserLine } from 'react-icons/ri';

import { useUpdateName, type AccountProfile } from '@/services/api/account';
import { useAuthStore } from '@/store/authStore';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Button } from '@/components/ui/button';
import { Loader } from '@/components/ui/Loader';

const nameSchema = z.object({
  full_name: z
    .string()
    .min(2, 'Name must be at least 2 characters.')
    .max(255, 'Name is too long.'),
});

type NameFormValues = z.infer<typeof nameSchema>;

const ROLE_BADGES: Record<string, { label: string; className: string }> = {
  OWNER: {
    label: 'Owner',
    className:
      'bg-indigo-50 text-indigo-700 border border-indigo-200 dark:bg-indigo-950/30 dark:text-indigo-400 dark:border-indigo-900/50',
  },
  ADMIN: {
    label: 'Admin',
    className:
      'bg-amber-50 text-amber-700 border border-amber-200 dark:bg-amber-950/30 dark:text-amber-400 dark:border-amber-900/50',
  },
  AGENT: {
    label: 'Agent',
    className:
      'bg-zinc-100 text-zinc-600 border border-zinc-200 dark:bg-zinc-800/50 dark:text-zinc-400 dark:border-zinc-700',
  },
};

interface ProfileTabProps {
  profile: AccountProfile;
}

export const ProfileTab = ({ profile }: ProfileTabProps) => {
  const updateUser = useAuthStore((s) => s.updateUser);
  const mutation = useUpdateName();

  const badge = ROLE_BADGES[profile.role?.toUpperCase()] ?? ROLE_BADGES.AGENT;

  const {
    register,
    handleSubmit,
    formState: { errors, isDirty },
  } = useForm<NameFormValues>({
    resolver: zodResolver(nameSchema),
    defaultValues: { full_name: profile.full_name },
  });

  const onSubmit = async (values: NameFormValues) => {
    try {
      await mutation.mutateAsync(values.full_name);
      // Sync auth store so Header reflects the new name immediately
      updateUser({ full_name: values.full_name });
      toast.success('Display name updated successfully.');
    } catch (err) {
      toast.error((err as Error).message || 'Failed to update name.');
    }
  };

  return (
    <div className="space-y-6">
      {/* Avatar / Info Card */}
      <div className="flex items-center gap-4 p-4 bg-zinc-50 dark:bg-zinc-800/40 rounded-2xl border border-zinc-100 dark:border-zinc-800">
        <div className="w-14 h-14 rounded-2xl bg-gradient-to-br from-indigo-400 to-violet-600 flex items-center justify-center text-white shadow-lg shrink-0">
          <RiUser3Line size={26} />
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-base font-bold text-zinc-900 dark:text-white truncate">
            {profile.full_name}
          </p>
          <p className="text-xs text-zinc-500 truncate mt-0.5">{profile.email}</p>
          <span
            className={`inline-flex items-center gap-1 mt-1.5 px-2.5 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider ${badge.className}`}
          >
            <RiShieldUserLine size={11} />
            {badge.label}
          </span>
        </div>
      </div>

      {/* Metadata */}
      <div className="grid grid-cols-2 gap-4">
        {profile.created_at && (
          <div>
            <p className="text-[10px] font-bold text-zinc-400 uppercase tracking-wider">Member Since</p>
            <p className="text-xs text-zinc-700 dark:text-zinc-300 mt-0.5 font-medium">
              {new Date(profile.created_at).toLocaleDateString(undefined, { dateStyle: 'medium' })}
            </p>
          </div>
        )}
        {profile.last_login_at && (
          <div>
            <p className="text-[10px] font-bold text-zinc-400 uppercase tracking-wider">Last Login</p>
            <p className="text-xs text-zinc-700 dark:text-zinc-300 mt-0.5 font-medium">
              {new Date(profile.last_login_at).toLocaleDateString(undefined, { dateStyle: 'medium' })}
            </p>
          </div>
        )}
      </div>

      {/* Name Form */}
      <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
        <div className="space-y-2">
          <Label htmlFor="full_name" className="text-sm font-semibold text-zinc-700 dark:text-zinc-300">
            Display Name
          </Label>
          <Input
            id="full_name"
            type="text"
            placeholder="Your full name"
            className="bg-zinc-50 dark:bg-zinc-800 border-zinc-200 dark:border-zinc-700"
            {...register('full_name')}
          />
          {errors.full_name && (
            <p className="text-xs text-red-500">{errors.full_name.message}</p>
          )}
        </div>

        <Button
          type="submit"
          disabled={mutation.isPending || !isDirty}
          className="w-full bg-primary text-white font-semibold rounded-xl hover:bg-primary/90 transition-all flex items-center justify-center gap-2"
        >
          {mutation.isPending ? (
            <Loader size="sm" className="text-white" />
          ) : (
            <RiCheckLine size={16} />
          )}
          Save Name
        </Button>
      </form>
    </div>
  );
};
