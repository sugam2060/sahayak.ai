'use client';

import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import * as z from 'zod';
import { toast } from 'sonner';
import { RiLockPasswordLine, RiEyeLine, RiEyeOffLine, RiCheckLine } from 'react-icons/ri';

import { useUpdatePassword } from '@/services/api/account';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Button } from '@/components/ui/button';
import { Loader } from '@/components/ui/Loader';

const passwordSchema = z
  .object({
    current_password: z.string().min(1, 'Current password is required.'),
    new_password: z
      .string()
      .min(8, 'New password must be at least 8 characters.'),
    confirm_password: z.string().min(1, 'Please confirm your new password.'),
  })
  .refine((d) => d.new_password === d.confirm_password, {
    message: "Passwords don't match.",
    path: ['confirm_password'],
  });

type PasswordFormValues = z.infer<typeof passwordSchema>;

/** Returns a strength score 0–4 and label. */
function getPasswordStrength(pwd: string): { score: number; label: string; color: string } {
  if (!pwd) return { score: 0, label: '', color: '' };
  let score = 0;
  if (pwd.length >= 8) score++;
  if (pwd.length >= 12) score++;
  if (/[A-Z]/.test(pwd) && /[a-z]/.test(pwd)) score++;
  if (/\d/.test(pwd)) score++;
  if (/[^A-Za-z0-9]/.test(pwd)) score++;

  const clipped = Math.min(score, 4) as 0 | 1 | 2 | 3 | 4;
  const labels = ['', 'Weak', 'Fair', 'Good', 'Strong'];
  const colors = ['', 'bg-red-500', 'bg-amber-400', 'bg-blue-500', 'bg-emerald-500'];
  return { score: clipped, label: labels[clipped], color: colors[clipped] };
}

export const PasswordTab = () => {
  const mutation = useUpdatePassword();
  const [showCurrent, setShowCurrent] = useState(false);
  const [showNew, setShowNew] = useState(false);
  const [newPwd, setNewPwd] = useState('');

  const strength = getPasswordStrength(newPwd);

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<PasswordFormValues>({
    resolver: zodResolver(passwordSchema),
  });

  const onSubmit = async (values: PasswordFormValues) => {
    try {
      await mutation.mutateAsync(values);
      toast.success('Password updated. Please use your new password next time you log in.');
      reset();
      setNewPwd('');
    } catch (err) {
      toast.error((err as Error).message || 'Failed to update password.');
    }
  };

  return (
    <div className="space-y-5">
      <div className="flex items-start gap-3 p-3 bg-amber-50 dark:bg-amber-950/20 border border-amber-200/70 dark:border-amber-900/30 rounded-xl">
        <RiLockPasswordLine size={18} className="text-amber-600 dark:text-amber-400 mt-0.5 shrink-0" />
        <p className="text-xs text-amber-700 dark:text-amber-300 leading-relaxed">
          Your new password must be at least 8 characters. After changing, your active sessions will
          be refreshed on the next request.
        </p>
      </div>

      <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
        {/* Current Password */}
        <div className="space-y-2">
          <Label htmlFor="current_password" className="text-sm font-semibold text-zinc-700 dark:text-zinc-300">
            Current Password
          </Label>
          <div className="relative">
            <Input
              id="current_password"
              type={showCurrent ? 'text' : 'password'}
              placeholder="Your current password"
              className="bg-zinc-50 dark:bg-zinc-800 border-zinc-200 dark:border-zinc-700 pr-10"
              {...register('current_password')}
            />
            <button
              type="button"
              onClick={() => setShowCurrent((v) => !v)}
              className="absolute right-3 top-1/2 -translate-y-1/2 text-zinc-400 hover:text-zinc-600 dark:hover:text-zinc-300 transition-colors"
              tabIndex={-1}
            >
              {showCurrent ? <RiEyeOffLine size={16} /> : <RiEyeLine size={16} />}
            </button>
          </div>
          {errors.current_password && (
            <p className="text-xs text-red-500">{errors.current_password.message}</p>
          )}
        </div>

        {/* New Password */}
        <div className="space-y-2">
          <Label htmlFor="new_password" className="text-sm font-semibold text-zinc-700 dark:text-zinc-300">
            New Password
          </Label>
          <div className="relative">
            <Input
              id="new_password"
              type={showNew ? 'text' : 'password'}
              placeholder="Min. 8 characters"
              className="bg-zinc-50 dark:bg-zinc-800 border-zinc-200 dark:border-zinc-700 pr-10"
              {...register('new_password', {
                onChange: (e) => setNewPwd(e.target.value),
              })}
            />
            <button
              type="button"
              onClick={() => setShowNew((v) => !v)}
              className="absolute right-3 top-1/2 -translate-y-1/2 text-zinc-400 hover:text-zinc-600 dark:hover:text-zinc-300 transition-colors"
              tabIndex={-1}
            >
              {showNew ? <RiEyeOffLine size={16} /> : <RiEyeLine size={16} />}
            </button>
          </div>

          {/* Password strength bar */}
          {newPwd && (
            <div className="space-y-1 pt-1">
              <div className="flex gap-1">
                {[1, 2, 3, 4].map((i) => (
                  <div
                    key={i}
                    className={`h-1 flex-1 rounded-full transition-all duration-300 ${
                      strength.score >= i ? strength.color : 'bg-zinc-200 dark:bg-zinc-700'
                    }`}
                  />
                ))}
              </div>
              {strength.label && (
                <p className="text-[10px] font-semibold text-zinc-500 dark:text-zinc-400">
                  Strength: <span className="text-zinc-700 dark:text-zinc-200">{strength.label}</span>
                </p>
              )}
            </div>
          )}

          {errors.new_password && (
            <p className="text-xs text-red-500">{errors.new_password.message}</p>
          )}
        </div>

        {/* Confirm Password */}
        <div className="space-y-2">
          <Label htmlFor="confirm_password" className="text-sm font-semibold text-zinc-700 dark:text-zinc-300">
            Confirm New Password
          </Label>
          <Input
            id="confirm_password"
            type="password"
            placeholder="Repeat new password"
            className="bg-zinc-50 dark:bg-zinc-800 border-zinc-200 dark:border-zinc-700"
            {...register('confirm_password')}
          />
          {errors.confirm_password && (
            <p className="text-xs text-red-500">{errors.confirm_password.message}</p>
          )}
        </div>

        <Button
          type="submit"
          disabled={mutation.isPending}
          className="w-full bg-primary text-white font-semibold rounded-xl hover:bg-primary/90 transition-all flex items-center justify-center gap-2"
        >
          {mutation.isPending ? (
            <Loader size="sm" className="text-white" />
          ) : (
            <RiCheckLine size={16} />
          )}
          Update Password
        </Button>
      </form>
    </div>
  );
};
