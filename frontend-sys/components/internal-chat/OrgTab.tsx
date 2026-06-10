'use client';

import React from 'react';
import { useOrgHistory } from '@/services/api/internal-chats';
import { ChatPane } from './ChatPane';

interface OrgTabProps {
  currentUserId: string;
  currentUserRole: string;
  onSendMessage: (convoId: string, text: string) => void;
}

export const OrgTab: React.FC<OrgTabProps> = ({
  currentUserId,
  currentUserRole,
  onSendMessage,
}) => {
  const { data: orgData, isLoading } = useOrgHistory();

  // Write permissions controlled by role (OWNER and ADMIN can write, AGENT is read-only)
  const isAgent = currentUserRole.toUpperCase() === 'AGENT';

  return (
    <div className="flex flex-col h-[440px] pt-1">
      <div className="pb-2 border-b border-zinc-200/50 dark:border-zinc-800/50 mb-2">
        <h3 className="text-sm font-bold text-zinc-900 dark:text-zinc-100">
          Organization Broadcast Channel
        </h3>
        <p className="text-[10px] text-zinc-400">
          Broadcast channel visible to all organization team members.
        </p>
      </div>

      {isLoading ? (
        <div className="flex-1 flex justify-center items-center">
          <div className="w-8 h-8 border-2 border-[#7C63D4] border-t-transparent rounded-full animate-spin" />
        </div>
      ) : (
        <ChatPane
          messages={orgData?.conversation?.messages || []}
          onSendMessage={(text) => {
            if (orgData?.conversation?._id) {
              onSendMessage(orgData.conversation._id, text);
            }
          }}
          currentUserId={currentUserId}
          placeholder="Broadcast an announcement..."
          readOnly={isAgent}
          readOnlyMessage="Only Owners and Admins can broadcast in this channel."
        />
      )}
    </div>
  );
};
