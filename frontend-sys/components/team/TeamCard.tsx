'use client';

import { Team, TeamMember } from '@/types/team';
import { useAssignTeamMember, useRemoveTeamMember } from '@/services/api/teams';
import { usePresenceStore } from '@/store/presenceStore';
import { toast } from 'sonner';
import { Button } from '@/components/ui/button';
import { Card, CardHeader, CardContent } from '@/components/ui/card';
import { Label } from '@/components/ui/label';
import { 
  Trash2, 
  Edit3, 
  UserMinus 
} from 'lucide-react';

interface TeamCardProps {
  team: Team;
  unassignedMembers: TeamMember[];
  onEdit: (team: Team) => void;
  onDelete: (teamId: string) => void;
  canManage: boolean;
}

export const TeamCard = ({ 
  team, 
  unassignedMembers, 
  onEdit, 
  onDelete, 
  canManage 
}: TeamCardProps) => {
  const assignMemberMutation = useAssignTeamMember();
  const removeMemberMutation = useRemoveTeamMember();
  const { statuses } = usePresenceStore();

  const handleAssign = async (userId: string) => {
    try {
      await assignMemberMutation.mutateAsync({ teamId: team.id, userId });
      toast.success('Member assigned to team.');
    } catch (error) {
      const errMsg = error instanceof Error ? error.message : 'Failed to assign member.';
      toast.error(errMsg);
    }
  };

  const handleRemove = async (userId: string) => {
    try {
      await removeMemberMutation.mutateAsync({ teamId: team.id, userId });
      toast.success('Member removed from team.');
    } catch (error) {
      const errMsg = error instanceof Error ? error.message : 'Failed to remove member.';
      toast.error(errMsg);
    }
  };

  return (
    <Card className="flex flex-col h-full bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-2xl overflow-hidden hover:shadow-md transition-shadow">
      <CardHeader className="flex flex-row items-start justify-between p-5 border-b border-zinc-100 dark:border-zinc-800">
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <h3 className="text-lg font-bold font-heading text-zinc-900 dark:text-white">
              {team.team_name}
            </h3>
            <span className="text-[10px] font-mono tracking-widest uppercase bg-indigo-50 dark:bg-indigo-950/40 text-primary px-2 py-0.5 rounded-full font-bold border border-indigo-100 dark:border-indigo-900/40">
              {team.role}
            </span>
          </div>
          {team.description && (
            <p className="text-xs text-zinc-500 dark:text-zinc-400 font-sans">
              {team.description}
            </p>
          )}
        </div>

        {canManage && (
          <div className="flex items-center gap-1">
            <Button
              variant="ghost"
              size="icon-sm"
              onClick={() => onEdit(team)}
              className="text-zinc-500 hover:text-zinc-900 dark:hover:text-white rounded-lg"
              title="Edit Team"
            >
              <Edit3 size={15} />
            </Button>
            <Button
              variant="ghost"
              size="icon-sm"
              onClick={() => onDelete(team.id)}
              className="text-zinc-500 hover:text-red-600 dark:hover:text-red-400 rounded-lg"
              title="Delete Team"
            >
              <Trash2 size={15} />
            </Button>
          </div>
        )}
      </CardHeader>

      <CardContent className="flex-1 p-5 flex flex-col justify-between space-y-4">
        {/* Permissions Badges */}
        {team.permissions && team.permissions.length > 0 && (
          <div className="space-y-1.5">
            <span className="text-[10px] font-bold font-mono tracking-wider uppercase text-zinc-400 dark:text-zinc-500">
              Permissions
            </span>
            <div className="flex flex-wrap gap-1">
              {team.permissions.map((perm) => {
                const friendlyLabels: Record<string, string> = {
                  products: 'Products Catalog',
                  orders: 'Orders Management',
                  tickets: 'Tickets Helpdesk',
                  connectors: 'Integration Connectors',
                  ai_config: 'AI Bot Config',
                  chats: 'Inbox Chat & Live Assist',
                  teams: 'Team Management',
                };
                return (
                  <span
                    key={perm}
                    className="text-[9px] font-bold bg-indigo-50/50 dark:bg-indigo-950/20 text-primary border border-indigo-100/50 dark:border-indigo-900/20 px-2 py-0.5 rounded-full"
                  >
                    {friendlyLabels[perm] || perm}
                  </span>
                );
              })}
            </div>
          </div>
        )}

        {/* Members List */}
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold font-mono tracking-wider uppercase text-zinc-400 dark:text-zinc-500">
              Members ({team.members.length})
            </span>
          </div>

          {team.members.length === 0 ? (
            <p className="text-xs text-zinc-400 dark:text-zinc-500 italic py-2 font-sans">
              No members assigned to this team yet.
            </p>
          ) : (
            <div className="space-y-2 max-h-[160px] overflow-y-auto pr-1">
              {team.members.map((member) => {
                const memberStatus = statuses[member.user_id] || 'offline';
                return (
                  <div 
                    key={member.user_id} 
                    className="flex items-center justify-between p-2.5 rounded-xl bg-zinc-50 dark:bg-zinc-800/50 border border-zinc-100 dark:border-zinc-800/30 group"
                  >
                    <div className="flex items-center gap-2.5 min-w-0">
                      <div className="w-8 h-8 rounded-full bg-zinc-200 dark:bg-zinc-700 flex items-center justify-center text-xs font-bold text-zinc-600 dark:text-zinc-300 relative">
                        {member.full_name.charAt(0).toUpperCase()}
                        <span 
                          className={`absolute -bottom-0.5 -right-0.5 w-3 h-3 rounded-full border-2 border-white dark:border-zinc-900 ${
                            memberStatus === 'online' ? 'bg-emerald-500' :
                            memberStatus === 'away' ? 'bg-amber-500' :
                            memberStatus === 'busy' ? 'bg-red-600' :
                            'bg-zinc-400'
                          }`}
                          title={`Status: ${memberStatus}`}
                        />
                      </div>
                      <div className="min-w-0">
                        <p className="text-xs font-semibold text-zinc-800 dark:text-zinc-200 truncate font-sans">
                          {member.full_name}
                        </p>
                        <p className="text-[10px] text-zinc-400 dark:text-zinc-500 truncate font-sans">
                          {member.email}
                        </p>
                      </div>
                    </div>

                    <div className="flex items-center gap-1.5 shrink-0">
                      <span className="text-[9px] font-bold tracking-wider uppercase bg-zinc-100 dark:bg-zinc-800 text-zinc-500 dark:text-zinc-400 px-1.5 py-0.5 rounded font-mono">
                        {member.role}
                      </span>

                      {canManage && (
                        <Button
                          variant="ghost"
                          size="icon-xs"
                          onClick={() => handleRemove(member.user_id)}
                          className="text-zinc-400 hover:text-red-500 opacity-0 group-hover:opacity-100 transition-opacity duration-150 rounded"
                          title="Remove from team"
                        >
                          <UserMinus size={13} />
                        </Button>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* Assign Selector */}
        {canManage && unassignedMembers.length > 0 && (
          <div className="pt-3 border-t border-zinc-100 dark:border-zinc-800 space-y-2">
            <Label className="text-xs font-semibold text-zinc-600 dark:text-zinc-400">
              Assign Existing Member
            </Label>
            <div className="flex gap-2">
              <select
                defaultValue=""
                onChange={(e) => {
                  if (e.target.value) {
                    handleAssign(e.target.value);
                    e.target.value = "";
                  }
                }}
                className="flex-1 bg-zinc-50 dark:bg-zinc-800 border border-zinc-200 dark:border-zinc-700 rounded-lg px-2.5 py-1.5 text-xs text-zinc-800 dark:text-zinc-200 focus:outline-none focus:ring-1 focus:ring-primary"
              >
                <option value="" disabled>Select member...</option>
                {unassignedMembers.map((m) => (
                  <option key={m.user_id} value={m.user_id}>
                    {m.full_name} ({m.email})
                  </option>
                ))}
              </select>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
};
