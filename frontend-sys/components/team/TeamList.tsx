'use client';

import { useState } from 'react';
import { useTeams, useUnassignedMembers, useDeleteTeam } from '@/services/api/teams';
import { Team } from '@/types/team';
import { TeamCard } from './TeamCard';
import { CreateTeamModal } from './CreateTeamModal';
import { InviteModal } from './InviteModal';
import { Button } from '@/components/ui/button';
import { Loader } from '@/components/ui/Loader';
import { toast } from 'sonner';
import { 
  Users, 
  UserPlus, 
  FolderPlus, 
  Mail, 
  ShieldAlert 
} from 'lucide-react';
import { useAuthStore } from '@/store/authStore';

export const TeamList = () => {
  const { data: teams = [], isLoading, error } = useTeams();
  const { data: unassignedMembers = [] } = useUnassignedMembers();
  const deleteTeamMutation = useDeleteTeam();
  const { user } = useAuthStore();

  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [isInviteOpen, setIsInviteOpen] = useState(false);
  const [selectedTeamForEdit, setSelectedTeamForEdit] = useState<Team | null>(null);
  const [preselectedTeamId, setPreselectedTeamId] = useState('');

  // Validate authorization permissions
  const userRole = user?.role?.toUpperCase();
  const userPermissions = user?.permissions || [];
  const canManage = userRole === 'OWNER' || userPermissions.includes('teams');

  const handleDeleteTeam = async (id: string) => {
    if (confirm('Are you sure you want to delete this team? All memberships will be unassigned.')) {
      try {
        await deleteTeamMutation.mutateAsync(id);
        toast.success('Team deleted successfully.');
      } catch (err) {
        const errMsg = err instanceof Error ? err.message : 'Failed to delete team.';
        toast.error(errMsg);
      }
    }
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <Loader size="lg" text="Loading Teams Workspace..." />
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center p-6 border border-zinc-200 dark:border-zinc-800 rounded-2xl bg-white dark:bg-zinc-900 text-center space-y-3 min-h-[300px]">
        <ShieldAlert className="h-12 w-12 text-red-500" />
        <h3 className="text-lg font-bold text-zinc-900 dark:text-white font-heading">Failed to Load Teams</h3>
        <p className="text-sm text-zinc-500 dark:text-zinc-400 font-sans max-w-md">
          {error.message || 'An error occurred while fetching teams list.'}
        </p>
      </div>
    );
  }

  // Calculate statistics
  const totalTeams = teams.length;
  const totalAssignedMembers = teams.reduce((acc, t) => acc + t.members.length, 0);
  const totalUnassigned = unassignedMembers.length;
  const totalMembers = totalAssignedMembers + totalUnassigned;
  const activeMembers = teams.reduce((acc, t) => acc + t.members.filter(m => m.is_active).length, 0) + unassignedMembers.filter(m => m.is_active).length;
  const pendingMembers = totalMembers - activeMembers;

  return (
    <div className="space-y-6">
      {/* Stats Summary Bar */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {[
          { label: 'Total Teams', value: totalTeams, icon: Users, color: 'text-indigo-500 bg-indigo-50 dark:bg-indigo-950/30' },
          { label: 'Total Members', value: totalMembers, icon: Users, color: 'text-emerald-500 bg-emerald-50 dark:bg-emerald-950/30' },
          { label: 'Active Members', value: activeMembers, icon: Users, color: 'text-teal-500 bg-teal-50 dark:bg-teal-950/30' },
          { label: 'Pending Invites', value: pendingMembers, icon: Mail, color: 'text-amber-500 bg-amber-50 dark:bg-amber-950/30' }
        ].map((stat, i) => (
          <div key={i} className="flex items-center gap-4 bg-white dark:bg-zinc-900 p-4 border border-zinc-200 dark:border-zinc-800 rounded-2xl shadow-sm">
            <div className={`p-2.5 rounded-xl ${stat.color}`}>
              <stat.icon size={20} />
            </div>
            <div>
              <p className="text-xs text-zinc-500 dark:text-zinc-400 font-medium">{stat.label}</p>
              <p className="text-xl font-bold font-heading text-zinc-900 dark:text-white">{stat.value}</p>
            </div>
          </div>
        ))}
      </div>

      {/* Action Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h2 className="text-2xl font-bold font-heading text-zinc-900 dark:text-white">Teams Workspace</h2>
          <p className="text-sm text-zinc-500 dark:text-zinc-400 font-sans">
            Manage your organization&apos;s support groups, assign staff roles, and invite new members.
          </p>
        </div>

        {canManage && (
          <div className="flex gap-2 shrink-0">
            <Button
              onClick={() => {
                setSelectedTeamForEdit(null);
                setIsCreateOpen(true);
              }}
              variant="outline"
              className="border border-zinc-200 dark:border-zinc-700 text-zinc-700 dark:text-zinc-300 rounded-lg px-4 py-2 hover:bg-zinc-50 dark:hover:bg-zinc-800 flex items-center gap-1.5 font-semibold"
            >
              <FolderPlus size={16} />
              Create Team
            </Button>
            <Button
              onClick={() => {
                setPreselectedTeamId('');
                setIsInviteOpen(true);
              }}
              className="bg-primary hover:bg-primary/95 text-white font-semibold rounded-lg px-4 py-2 flex items-center gap-1.5 shadow-sm shadow-primary/20"
            >
              <UserPlus size={16} />
              Invite Member
            </Button>
          </div>
        )}
      </div>

      {/* Main Teams Grid */}
      {teams.length === 0 ? (
        <div className="flex flex-col items-center justify-center p-12 border border-dashed border-zinc-300 dark:border-zinc-800 rounded-2xl text-center space-y-4 min-h-[300px] bg-white dark:bg-zinc-900/50">
          <div className="h-16 w-16 bg-zinc-50 dark:bg-zinc-800 flex items-center justify-center rounded-2xl text-zinc-400 border border-zinc-200 dark:border-zinc-700">
            <Users size={32} />
          </div>
          <div className="space-y-1">
            <h3 className="text-lg font-bold text-zinc-900 dark:text-white font-heading">No Teams Created Yet</h3>
            <p className="text-sm text-zinc-500 dark:text-zinc-400 font-sans max-w-sm">
              Organize your support agents into teams based on their business channels or skills.
            </p>
          </div>
          {canManage && (
            <Button
              onClick={() => {
                setSelectedTeamForEdit(null);
                setIsCreateOpen(true);
              }}
              className="bg-primary hover:bg-primary/95 text-white font-semibold rounded-lg px-4 py-2 flex items-center gap-1.5 shadow-sm shadow-primary/20"
            >
              <FolderPlus size={16} />
              Create Your First Team
            </Button>
          )}
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {teams.map((team) => (
            <TeamCard
              key={team.id}
              team={team}
              unassignedMembers={unassignedMembers}
              onEdit={(t) => {
                setSelectedTeamForEdit(t);
                setIsCreateOpen(true);
              }}
              onDelete={handleDeleteTeam}
              canManage={canManage}
            />
          ))}
        </div>
      )}

      {/* Modals */}
      <CreateTeamModal
        isOpen={isCreateOpen}
        onClose={() => {
          setIsCreateOpen(false);
          setSelectedTeamForEdit(null);
        }}
        teamToEdit={selectedTeamForEdit}
      />

      <InviteModal
        isOpen={isInviteOpen}
        onClose={() => setIsInviteOpen(false)}
        preselectedTeamId={preselectedTeamId}
      />
    </div>
  );
};
