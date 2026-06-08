'use client';

import { useEffect } from 'react';
import { useForm, useWatch } from 'react-hook-form';
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
import { Checkbox } from '@/components/ui/checkbox';
import { useCreateTeam, useUpdateTeam } from '@/services/api/teams';
import { Team } from '@/types/team';

const teamSchema = z.object({
  team_name: z.string().min(1, 'Team name is required').max(255),
  description: z.string().optional().or(z.literal('')),
  role: z.string().min(1, 'Team role is required').max(100),
  permissions: z.array(z.string()),
});

type TeamFormValues = z.infer<typeof teamSchema>;

interface CreateTeamModalProps {
  isOpen: boolean;
  onClose: () => void;
  teamToEdit?: Team | null;
}

const AVAILABLE_PERMISSIONS = [
  { id: 'products', label: 'Products Catalog', description: 'View and manage the product catalog' },
  { id: 'orders', label: 'Orders Management', description: 'View, create, and update order statuses' },
  { id: 'tickets', label: 'Tickets Helpdesk', description: 'Manage customer support tickets' },
  { id: 'connectors', label: 'Integration Connectors', description: 'Connect third-party platforms (Telegram, Instagram)' },
  { id: 'ai_config', label: 'AI Bot Configuration', description: 'Manage AI agent settings and prompts' },
  { id: 'chats', label: 'Inbox Chat & Live Assist', description: 'Read, reply, assign and mark chats as read' },
  { id: 'teams', label: 'Team Management', description: 'Create teams and configure user assignments' },
  { id: 'org_settings', label: 'Organization Settings', description: 'Manage organization settings, name, and delete options' },
];

export const CreateTeamModal = ({ isOpen, onClose, teamToEdit }: CreateTeamModalProps) => {
  const createTeamMutation = useCreateTeam();
  const updateTeamMutation = useUpdateTeam();

  const {
    register,
    handleSubmit,
    reset,
    setValue,
    control,
    formState: { errors, isSubmitting },
  } = useForm<TeamFormValues>({
    resolver: zodResolver(teamSchema),
    defaultValues: {
      team_name: '',
      description: '',
      role: 'AGENT',
      permissions: [],
    },
  });

  useEffect(() => {
    if (teamToEdit) {
      reset({
        team_name: teamToEdit.team_name,
        description: teamToEdit.description || '',
        role: teamToEdit.role || 'AGENT',
        permissions: teamToEdit.permissions || [],
      });
    } else {
      reset({
        team_name: '',
        description: '',
        role: 'AGENT',
        permissions: [],
      });
    }
  }, [teamToEdit, reset, isOpen]);

  const selectedPermissions = useWatch({
    control,
    name: 'permissions',
  }) || [];

  const handlePermissionChange = (permId: string, checked: boolean) => {
    if (checked) {
      setValue('permissions', [...selectedPermissions, permId]);
    } else {
      setValue('permissions', selectedPermissions.filter((id) => id !== permId));
    }
  };

  const onSubmit = async (values: TeamFormValues) => {
    try {
      if (teamToEdit) {
        await updateTeamMutation.mutateAsync({
          id: teamToEdit.id,
          data: values,
        });
        toast.success('Team updated successfully.');
      } else {
        await createTeamMutation.mutateAsync(values);
        toast.success('Team created successfully.');
      }
      onClose();
    } catch (error) {
      const errMsg = error instanceof Error ? error.message : 'An error occurred.';
      toast.error(errMsg);
    }
  };

  return (
    <Dialog open={isOpen} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="sm:max-w-md bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-2xl p-6">
        <DialogHeader>
          <DialogTitle className="text-xl font-bold font-heading text-zinc-900 dark:text-white">
            {teamToEdit ? 'Edit Team' : 'Create Team'}
          </DialogTitle>
          <DialogDescription className="sr-only">
            Provide details to create or configure a support group team.
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4 py-2">
          <div className="space-y-2">
            <Label htmlFor="team_name" className="text-sm font-semibold text-zinc-700 dark:text-zinc-300">
              Team Name
            </Label>
            <Input
              id="team_name"
              type="text"
              placeholder="e.g. Support Squad"
              className="w-full bg-zinc-50 dark:bg-zinc-800 border border-zinc-200 dark:border-zinc-700 rounded-lg px-3 py-2 text-sm text-zinc-900 dark:text-white placeholder-zinc-400 focus:outline-none"
              {...register('team_name')}
            />
            {errors.team_name && (
              <p className="text-xs text-red-500 font-sans">{errors.team_name.message}</p>
            )}
          </div>

          <div className="space-y-2">
            <Label htmlFor="description" className="text-sm font-semibold text-zinc-700 dark:text-zinc-300">
              Description
            </Label>
            <Input
              id="description"
              type="text"
              placeholder="Brief summary of the team's objectives"
              className="w-full bg-zinc-50 dark:bg-zinc-800 border border-zinc-200 dark:border-zinc-700 rounded-lg px-3 py-2 text-sm text-zinc-900 dark:text-white placeholder-zinc-400 focus:outline-none"
              {...register('description')}
            />
            {errors.description && (
              <p className="text-xs text-red-500 font-sans">{errors.description.message}</p>
            )}
          </div>

          <div className="space-y-2">
            <Label htmlFor="role" className="text-sm font-semibold text-zinc-700 dark:text-zinc-300">
              Team Role / Skill
            </Label>
            <Input
              id="role"
              type="text"
              placeholder="e.g. AGENT, ADMIN, SUPPORT"
              className="w-full bg-zinc-50 dark:bg-zinc-800 border border-zinc-200 dark:border-zinc-700 rounded-lg px-3 py-2 text-sm text-zinc-900 dark:text-white placeholder-zinc-400 focus:outline-none"
              {...register('role')}
            />
            {errors.role && (
              <p className="text-xs text-red-500 font-sans">{errors.role.message}</p>
            )}
          </div>

          <div className="space-y-3">
            <Label className="text-sm font-semibold text-zinc-700 dark:text-zinc-300">
              Team Permissions
            </Label>
            <div className="grid grid-cols-1 gap-2.5 max-h-48 overflow-y-auto pr-1 border border-zinc-200 dark:border-zinc-800 rounded-lg p-3 bg-zinc-55 dark:bg-zinc-950">
              {AVAILABLE_PERMISSIONS.map((perm) => (
                <div key={perm.id} className="flex items-start gap-3 p-1.5 rounded hover:bg-zinc-100/50 dark:hover:bg-zinc-800/50 transition-colors">
                  <Checkbox
                    id={`perm-${perm.id}`}
                    checked={selectedPermissions.includes(perm.id)}
                    onCheckedChange={(checked) => handlePermissionChange(perm.id, !!checked)}
                    className="mt-0.5"
                  />
                  <div className="grid gap-0.5 leading-none">
                    <label
                      htmlFor={`perm-${perm.id}`}
                      className="text-xs font-semibold text-zinc-800 dark:text-zinc-200 cursor-pointer select-none"
                    >
                      {perm.label}
                    </label>
                    <span className="text-[10px] text-zinc-500 dark:text-zinc-400">
                      {perm.description}
                    </span>
                  </div>
                </div>
              ))}
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
              {isSubmitting ? 'Saving...' : teamToEdit ? 'Save Changes' : 'Create Team'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
};
