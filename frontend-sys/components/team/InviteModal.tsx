'use client';

import { useEffect } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import * as z from 'zod';
import { toast } from 'sonner';
import { 
  Dialog, 
  DialogContent, 
  DialogDescription,
  DialogHeader, 
  DialogTitle, 
  DialogFooter 
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { useInviteMember, useTeams } from '@/services/api/teams';

const inviteSchema = z.object({
  full_name: z.string().min(1, 'Full name is required').max(255),
  email: z.string().email('Please enter a valid email address'),
  password: z.string().min(6, 'Password must be at least 6 characters long').max(255),
  role: z.enum(['ADMIN', 'AGENT']),
  team_id: z.string().optional().or(z.literal('')),
});

type InviteFormValues = z.infer<typeof inviteSchema>;

interface InviteModalProps {
  isOpen: boolean;
  onClose: () => void;
  preselectedTeamId?: string;
}

export const InviteModal = ({ isOpen, onClose, preselectedTeamId }: InviteModalProps) => {
  const inviteMutation = useInviteMember();
  const { data: teams = [] } = useTeams();

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors, isSubmitting },
  } = useForm<InviteFormValues>({
    resolver: zodResolver(inviteSchema),
    defaultValues: {
      full_name: '',
      email: '',
      password: '',
      role: 'AGENT',
      team_id: '',
    },
  });

  useEffect(() => {
    reset({
      full_name: '',
      email: '',
      password: '',
      role: 'AGENT',
      team_id: preselectedTeamId || '',
    });
  }, [isOpen, preselectedTeamId, reset]);

  const onSubmit = async (values: InviteFormValues) => {
    try {
      const payload = {
        ...values,
        team_id: values.team_id === '' ? undefined : values.team_id,
      };
      await inviteMutation.mutateAsync(payload);
      toast.success('Member invited successfully. Verification email sent.');
      onClose();
    } catch (error) {
      const errMsg = error instanceof Error ? error.message : 'Failed to invite team member.';
      toast.error(errMsg);
    }
  };

  return (
    <Dialog open={isOpen} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="sm:max-w-md bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-2xl p-6">
        <DialogHeader>
          <DialogTitle className="text-xl font-bold font-heading text-zinc-900 dark:text-white">
            Invite Team Member
          </DialogTitle>
          <DialogDescription className="sr-only">
            Invite a new member to join your organization team.
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4 py-4">
          <div className="space-y-2">
            <Label htmlFor="full_name" className="text-sm font-semibold text-zinc-700 dark:text-zinc-300">
              Full Name
            </Label>
            <Input
              id="full_name"
              type="text"
              placeholder="e.g. John Doe"
              className="w-full bg-zinc-50 dark:bg-zinc-800 border border-zinc-200 dark:border-zinc-700 rounded-lg px-3 py-2 text-sm text-zinc-900 dark:text-white placeholder-zinc-400 focus:outline-none"
              {...register('full_name')}
            />
            {errors.full_name && (
              <p className="text-xs text-red-500 font-sans">{errors.full_name.message}</p>
            )}
          </div>

          <div className="space-y-2">
            <Label htmlFor="email" className="text-sm font-semibold text-zinc-700 dark:text-zinc-300">
              Email Address
            </Label>
            <Input
              id="email"
              type="email"
              placeholder="e.g. john@example.com"
              className="w-full bg-zinc-50 dark:bg-zinc-800 border border-zinc-200 dark:border-zinc-700 rounded-lg px-3 py-2 text-sm text-zinc-900 dark:text-white placeholder-zinc-400 focus:outline-none"
              {...register('email')}
            />
            {errors.email && (
              <p className="text-xs text-red-500 font-sans">{errors.email.message}</p>
            )}
          </div>

          <div className="space-y-2">
            <Label htmlFor="password" className="text-sm font-semibold text-zinc-700 dark:text-zinc-300">
              Password
            </Label>
            <Input
              id="password"
              type="password"
              placeholder="Temporary password for the user"
              className="w-full bg-zinc-50 dark:bg-zinc-800 border border-zinc-200 dark:border-zinc-700 rounded-lg px-3 py-2 text-sm text-zinc-900 dark:text-white placeholder-zinc-400 focus:outline-none"
              {...register('password')}
            />
            {errors.password && (
              <p className="text-xs text-red-500 font-sans">{errors.password.message}</p>
            )}
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="role" className="text-sm font-semibold text-zinc-700 dark:text-zinc-300">
                Organization Role
              </Label>
              <select
                id="role"
                className="w-full bg-zinc-50 dark:bg-zinc-800 border border-zinc-200 dark:border-zinc-700 rounded-lg px-3 py-2 text-sm text-zinc-900 dark:text-white placeholder-zinc-400 focus:outline-none focus:ring-1 focus:ring-primary"
                {...register('role')}
              >
                <option value="AGENT">AGENT</option>
                <option value="ADMIN">ADMIN</option>
              </select>
              {errors.role && (
                <p className="text-xs text-red-500 font-sans">{errors.role.message}</p>
              )}
            </div>

            <div className="space-y-2">
              <Label htmlFor="team_id" className="text-sm font-semibold text-zinc-700 dark:text-zinc-300">
                Assign Team
              </Label>
              <select
                id="team_id"
                className="w-full bg-zinc-50 dark:bg-zinc-800 border border-zinc-200 dark:border-zinc-700 rounded-lg px-3 py-2 text-sm text-zinc-900 dark:text-white placeholder-zinc-400 focus:outline-none focus:ring-1 focus:ring-primary"
                {...register('team_id')}
              >
                <option value="">No Team</option>
                {teams.map((t) => (
                  <option key={t.id} value={t.id}>
                    {t.team_name}
                  </option>
                ))}
              </select>
              {errors.team_id && (
                <p className="text-xs text-red-500 font-sans">{errors.team_id.message}</p>
              )}
            </div>
          </div>

          <DialogFooter className="pt-4 flex justify-end gap-2">
            <Button
              type="button"
              variant="outline"
              onClick={onClose}
              className="border border-zinc-200 dark:border-zinc-700 text-zinc-700 dark:text-zinc-300 rounded-lg px-4 py-2 hover:bg-zinc-50 dark:hover:bg-zinc-800"
            >
              Cancel
            </Button>
            <Button
              type="submit"
              disabled={isSubmitting}
              className="bg-primary hover:bg-primary/95 text-white font-semibold rounded-lg px-4 py-2 flex items-center justify-center gap-1.5"
            >
              {isSubmitting ? 'Inviting...' : 'Invite Member'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
};
