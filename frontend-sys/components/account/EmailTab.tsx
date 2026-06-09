'use client';

import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import * as z from 'zod';
import { toast } from 'sonner';
import { RiMailLine, RiMailSendLine, RiCheckboxCircleLine } from 'react-icons/ri';

import { useRequestEmailChange, type AccountProfile } from '@/services/api/account';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Button } from '@/components/ui/button';
import { Loader } from '@/components/ui/Loader';

const emailSchema = z.object({
  new_email: z.string().email('Please enter a valid email address.'),
});

type EmailFormValues = z.infer<typeof emailSchema>;

/** Mask an email so only the first 2 chars and domain are shown. */
function maskEmail(email: string): string {
  const [local, domain] = email.split('@');
  if (!local || !domain) return email;
  return `${local.slice(0, 2)}${'•'.repeat(Math.max(0, local.length - 2))}@${domain}`;
}

interface EmailTabProps {
  profile: AccountProfile;
}

export const EmailTab = ({ profile }: EmailTabProps) => {
  const mutation = useRequestEmailChange();
  const [sent, setSent] = useState(false);
  const [sentTo, setSentTo] = useState('');

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<EmailFormValues>({
    resolver: zodResolver(emailSchema),
  });

  const onSubmit = async (values: EmailFormValues) => {
    try {
      await mutation.mutateAsync(values.new_email);
      setSentTo(values.new_email);
      setSent(true);
    } catch (err) {
      toast.error((err as Error).message || 'Failed to request email change.');
    }
  };

  if (sent) {
    return (
      <div className="flex flex-col items-center justify-center text-center gap-4 py-6">
        <div className="w-16 h-16 rounded-2xl bg-emerald-50 dark:bg-emerald-950/30 flex items-center justify-center text-emerald-500">
          <RiCheckboxCircleLine size={36} />
        </div>
        <div>
          <h3 className="text-base font-bold text-zinc-900 dark:text-white">Check your inbox</h3>
          <p className="text-sm text-zinc-500 dark:text-zinc-400 mt-1 max-w-xs leading-relaxed">
            We sent a confirmation link to{' '}
            <span className="font-semibold text-zinc-700 dark:text-zinc-200">{sentTo}</span>.
            Click it to apply the change.
          </p>
        </div>
        <p className="text-xs text-zinc-400 dark:text-zinc-500">
          The link expires in 24 hours. Your current email remains active until confirmed.
        </p>
        <Button
          variant="outline"
          size="sm"
          onClick={() => setSent(false)}
          className="rounded-xl border-zinc-200 dark:border-zinc-700 text-xs"
        >
          Change a different address
        </Button>
      </div>
    );
  }

  return (
    <div className="space-y-5">
      {/* Current email display */}
      <div className="flex items-center gap-3 p-3 bg-zinc-50 dark:bg-zinc-800/40 rounded-xl border border-zinc-200 dark:border-zinc-800">
        <div className="w-8 h-8 rounded-lg bg-indigo-50 dark:bg-indigo-950/30 flex items-center justify-center text-indigo-500">
          <RiMailLine size={16} />
        </div>
        <div>
          <p className="text-[10px] font-bold text-zinc-400 uppercase tracking-wider">Current Email</p>
          <p className="text-sm font-semibold text-zinc-800 dark:text-zinc-200">
            {maskEmail(profile.email)}
          </p>
        </div>
      </div>

      <div className="flex items-start gap-3 p-3 bg-blue-50 dark:bg-blue-950/20 border border-blue-200/70 dark:border-blue-900/30 rounded-xl">
        <RiMailSendLine size={18} className="text-blue-600 dark:text-blue-400 mt-0.5 shrink-0" />
        <p className="text-xs text-blue-700 dark:text-blue-300 leading-relaxed">
          A verification link will be sent to your new address. Your email only changes after you
          click the link. Your current address stays active until then.
        </p>
      </div>

      <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
        <div className="space-y-2">
          <Label htmlFor="new_email" className="text-sm font-semibold text-zinc-700 dark:text-zinc-300">
            New Email Address
          </Label>
          <Input
            id="new_email"
            type="email"
            placeholder="your@newemail.com"
            className="bg-zinc-50 dark:bg-zinc-800 border-zinc-200 dark:border-zinc-700"
            {...register('new_email')}
          />
          {errors.new_email && (
            <p className="text-xs text-red-500">{errors.new_email.message}</p>
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
            <RiMailSendLine size={16} />
          )}
          Send Verification Email
        </Button>
      </form>
    </div>
  );
};
