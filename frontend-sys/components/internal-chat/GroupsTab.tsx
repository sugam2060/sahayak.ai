'use client';

import React, { useState } from 'react';
import { useGroupChats, useGroupHistory, useCreateGroup, useManageGroupMembers, useInternalMembers } from '@/services/api/internal-chats';
import { ChatPane } from './ChatPane';
import { InternalConversation } from '@/types/internal-chat';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { ChevronRight, Users, Plus, X, ShieldAlert, Check } from 'lucide-react';
import { toast } from 'sonner';

interface GroupsTabProps {
  currentUserId: string;
  onSendMessage: (groupId: string, text: string) => void;
}

export const GroupsTab: React.FC<GroupsTabProps> = ({ currentUserId, onSendMessage }) => {
  const [selectedGroup, setSelectedGroup] = useState<InternalConversation | null>(null);
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [groupName, setGroupName] = useState('');
  const [selectedMemberIds, setSelectedMemberIds] = useState<string[]>([]);
  const [showManageMembers, setShowManageMembers] = useState(false);

  // Queries
  const { data: groupsData, isLoading: loadingGroups } = useGroupChats();
  const { data: historyData, isLoading: loadingHistory } = useGroupHistory(selectedGroup?._id || null);
  const { data: membersData } = useInternalMembers();

  // Mutations
  const createMutation = useCreateGroup();
  const manageMembersMutation = useManageGroupMembers(selectedGroup?._id || '');

  const handleCreateGroup = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!groupName.trim()) {
      toast.error('Group name is required.');
      return;
    }
    
    try {
      await createMutation.mutateAsync({
        name: groupName,
        member_ids: selectedMemberIds,
      });
      toast.success('Group created successfully.');
      setGroupName('');
      setSelectedMemberIds([]);
      setShowCreateForm(false);
    } catch (err: unknown) {
      toast.error((err as Error).message || 'Failed to create group.');
    }
  };

  const handleToggleMember = (userId: string) => {
    setSelectedMemberIds((prev) =>
      prev.includes(userId) ? prev.filter((id) => id !== userId) : [...prev, userId]
    );
  };

  const handleAddRemoveMember = async (action: 'add' | 'remove', userId: string) => {
    try {
      await manageMembersMutation.mutateAsync({ action, user_id: userId });
      toast.success(`User ${action === 'add' ? 'added' : 'removed'} successfully.`);
    } catch (err: unknown) {
      toast.error((err as Error).message || 'Failed to update member list.');
    }
  };

  const isAdmin = selectedGroup?.group_admin_ids.includes(currentUserId);
  const allMembers = membersData?.members || [];
  const currentMembers = historyData?.conversation?.user_ids || [];

  return (
    <div className="grid grid-cols-5 gap-4 h-[440px] pt-1">
      {/* Group sidebar list */}
      <div className="col-span-2 border-r border-zinc-200/50 dark:border-zinc-800/50 pr-2 overflow-y-auto flex flex-col gap-1.5">
        <div className="flex items-center justify-between mb-1 px-1">
          <h3 className="text-xs font-bold text-zinc-400 dark:text-zinc-500 uppercase tracking-wider">
            Group Chats
          </h3>
          <Button
            size="icon-sm"
            variant="ghost"
            onClick={() => {
              setShowCreateForm(!showCreateForm);
              setSelectedGroup(null);
            }}
            className="h-5 w-5 rounded-full text-zinc-500 hover:bg-zinc-100 hover:text-zinc-850 cursor-pointer"
          >
            <Plus size={12} />
          </Button>
        </div>

        {loadingGroups ? (
          <div className="flex justify-center items-center py-8">
            <div className="w-5 h-5 border-2 border-[#7C63D4] border-t-transparent rounded-full animate-spin" />
          </div>
        ) : !showCreateForm && (groupsData?.groups || []).length === 0 ? (
          <div className="text-xs text-zinc-400 py-4 text-center">No groups created yet.</div>
        ) : showCreateForm ? (
          /* Create Group Form */
          <form onSubmit={handleCreateGroup} className="space-y-3 p-2 bg-zinc-50/50 dark:bg-zinc-900/10 border border-zinc-200/50 dark:border-zinc-800/50 rounded-xl animate-in fade-in-0">
            <div className="space-y-1">
              <span className="text-[10px] font-bold text-zinc-400 uppercase tracking-wide">Group Name</span>
              <Input
                value={groupName}
                onChange={(e) => setGroupName(e.target.value)}
                placeholder="Marketing Team..."
                className="h-8 text-xs bg-white dark:bg-zinc-900 border border-zinc-200/50 dark:border-zinc-800/50 rounded-lg"
              />
            </div>
            <div className="space-y-1.5">
              <span className="text-[10px] font-bold text-zinc-400 uppercase tracking-wide block">Add Members</span>
              <div className="max-h-24 overflow-y-auto space-y-1 pr-1 border border-zinc-200/20 rounded-lg p-1.5 bg-white/50 dark:bg-zinc-950/20">
                {allMembers.map((m) => {
                  const selected = selectedMemberIds.includes(m.user_id);
                  return (
                    <button
                      key={m.user_id}
                      type="button"
                      onClick={() => handleToggleMember(m.user_id)}
                      className={`w-full text-left px-2 py-1 rounded text-[10px] flex items-center justify-between border border-transparent transition-colors cursor-pointer ${
                        selected
                          ? 'bg-[#7C63D4]/10 text-[#7C63D4]'
                          : 'hover:bg-zinc-100 dark:hover:bg-zinc-900/50'
                      }`}
                    >
                      <span className="font-medium">{m.full_name}</span>
                      {selected && <Check size={10} />}
                    </button>
                  );
                })}
              </div>
            </div>
            <div className="flex gap-2 justify-end pt-1">
              <Button
                size="sm"
                variant="ghost"
                type="button"
                onClick={() => setShowCreateForm(false)}
                className="h-7 text-[10px] rounded-lg cursor-pointer"
              >
                Cancel
              </Button>
              <Button
                size="sm"
                type="submit"
                className="h-7 text-[10px] rounded-lg bg-gradient-to-br from-[#7C63D4] to-[#5E9EEB] text-white hover:opacity-90 cursor-pointer"
              >
                Create
              </Button>
            </div>
          </form>
        ) : (
          /* Groups List */
          (groupsData?.groups || []).map((g) => (
            <button
              key={g._id}
              onClick={() => {
                setSelectedGroup(g);
                setShowManageMembers(false);
              }}
              className={`w-full flex items-center justify-between p-2 rounded-xl text-left text-xs transition-all border cursor-pointer ${
                selectedGroup?._id === g._id
                  ? 'bg-zinc-100 dark:bg-zinc-900/50 border-zinc-200/60 dark:border-zinc-800 text-zinc-900 dark:text-zinc-100 font-medium'
                  : 'bg-transparent border-transparent hover:bg-zinc-50 dark:hover:bg-zinc-900/20 text-zinc-600 dark:text-zinc-400'
              }`}
            >
              <div className="flex items-center gap-2 min-w-0">
                <div className="w-6 h-6 rounded-lg bg-[#7C63D4]/10 text-primary flex items-center justify-center flex-shrink-0">
                  <Users size={12} />
                </div>
                <span className="font-semibold truncate">{g.group_name}</span>
              </div>
              <ChevronRight size={14} className="text-zinc-400" />
            </button>
          ))
        )}
      </div>

      {/* Group conversation window */}
      <div className="col-span-3 flex flex-col h-full min-w-0 justify-center">
        {selectedGroup ? (
          <div className="flex flex-col h-full min-w-0">
            {/* Header */}
            <div className="flex items-center justify-between pb-2 border-b border-zinc-200/50 dark:border-zinc-800/50 mb-2">
              <div className="min-w-0">
                <h4 className="text-sm font-bold text-zinc-900 dark:text-zinc-100 truncate">
                  {selectedGroup.group_name}
                </h4>
                <p className="text-[10px] text-zinc-400 truncate">
                  {currentMembers.length} member{currentMembers.length !== 1 ? 's' : ''}
                </p>
              </div>

              {isAdmin && (
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => setShowManageMembers(!showManageMembers)}
                  className="h-8 px-2.5 rounded-lg border-zinc-200 dark:border-zinc-800 text-xs gap-1 hover:bg-[#7C63D4]/10 hover:text-[#7C63D4] cursor-pointer"
                >
                  <Users size={12} />
                  Manage Members
                </Button>
              )}
            </div>

            {/* Chat Pane */}
            {loadingHistory ? (
              <div className="flex-1 flex justify-center items-center">
                <div className="w-8 h-8 border-2 border-[#7C63D4] border-t-transparent rounded-full animate-spin" />
              </div>
            ) : (
              <ChatPane
                messages={historyData?.conversation?.messages || []}
                onSendMessage={(text) => onSendMessage(selectedGroup._id, text)}
                currentUserId={currentUserId}
                placeholder={`Message ${selectedGroup.group_name}...`}
                extraActions={
                  showManageMembers && isAdmin ? (
                    <div className="w-full bg-zinc-50 dark:bg-zinc-900/50 border border-zinc-200 dark:border-zinc-800 p-2.5 rounded-xl text-left space-y-2 mt-1 z-10 shadow-lg animate-in fade-in-0 slide-in-from-bottom-2">
                      <div className="flex items-center justify-between">
                        <span className="text-[10px] font-bold text-zinc-500 uppercase tracking-wide flex items-center gap-1">
                          <ShieldAlert size={12} className="text-[#7C63D4]" />
                          Group Membership Settings
                        </span>
                        <Button
                          size="icon-sm"
                          variant="ghost"
                          onClick={() => setShowManageMembers(false)}
                          className="h-4 w-4 text-zinc-400 hover:text-zinc-600 rounded-full"
                        >
                          <X size={10} />
                        </Button>
                      </div>

                      <div className="max-h-24 overflow-y-auto space-y-1 pr-1">
                        {allMembers.map((m) => {
                          const isMember = currentMembers.includes(m.user_id);
                          return (
                            <div
                              key={m.user_id}
                              className="flex items-center justify-between p-1.5 rounded hover:bg-zinc-100 dark:hover:bg-zinc-900/30 text-[10px] border border-transparent"
                            >
                              <span className="font-semibold text-zinc-800 dark:text-zinc-200 truncate">
                                {m.full_name}
                              </span>
                              {isMember ? (
                                <Button
                                  size="sm"
                                  variant="ghost"
                                  onClick={() => handleAddRemoveMember('remove', m.user_id)}
                                  className="h-5 px-1.5 rounded bg-red-100 hover:bg-red-200 text-red-700 dark:bg-red-950/20 dark:text-red-400 text-[9px] cursor-pointer"
                                >
                                  Remove
                                </Button>
                              ) : (
                                <Button
                                  size="sm"
                                  variant="ghost"
                                  onClick={() => handleAddRemoveMember('add', m.user_id)}
                                  className="h-5 px-1.5 rounded bg-emerald-100 hover:bg-emerald-200 text-emerald-750 dark:bg-emerald-950/20 dark:text-emerald-400 text-[9px] cursor-pointer"
                                >
                                  Add
                                </Button>
                              )}
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  ) : null
                }
              />
            )}
          </div>
        ) : (
          <div className="h-full flex items-center justify-center text-zinc-400 dark:text-zinc-500 text-xs bg-zinc-50/20 dark:bg-zinc-900/10 border border-dashed border-zinc-200 dark:border-zinc-800 rounded-xl p-6 text-center">
            Select or create a group chat.
          </div>
        )}
      </div>
    </div>
  );
};
