'use client';

import React, { useState, useEffect } from 'react';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from '@/components/ui/dialog';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { DirectTab } from './DirectTab';
import { GroupsTab } from './GroupsTab';
import { OrgTab } from './OrgTab';
import { MessageSquare, Users, Radio } from 'lucide-react';
import { useUnreadStore } from '@/store/unreadStore';

interface InternalChatDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  currentUserId: string;
  currentUserRole: string;
  onSendWSMessage: (convoId: string, text: string, type: 'direct' | 'group' | 'org', msgType?: 'text' | 'customer_chat_request', customerReqData?: unknown) => void;
}

export const InternalChatDialog: React.FC<InternalChatDialogProps> = ({
  open,
  onOpenChange,
  currentUserId,
  currentUserRole,
  onSendWSMessage,
}) => {
  const [activeTab, setActiveTab] = useState('direct');
  const setActiveKey = useUnreadStore((state) => state.setActiveKey);

  useEffect(() => {
    if (!open) {
      setActiveKey(null);
    } else {
      if (activeTab === 'org') {
        setActiveKey('org');
      }
    }
  }, [open, activeTab, setActiveKey]);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-xl md:max-w-2xl bg-white/85 dark:bg-zinc-950/85 backdrop-blur-xl border border-zinc-200/50 dark:border-zinc-800/80 rounded-2xl shadow-2xl p-4 gap-4 text-zinc-900 dark:text-zinc-100 flex flex-col font-sans select-none overflow-hidden">
        
        {/* Custom Header with close button override if needed, shadcn already handles close */}
        <DialogHeader className="border-b border-zinc-200/50 dark:border-zinc-800/50 pb-2 flex-row justify-between items-center space-y-0">
          <div>
            <DialogTitle className="text-base font-bold font-heading brand-text-gradient bg-gradient-to-r from-[#7C63D4] to-[#5E9EEB]">
              Sahayak Internal Workspace Chat
            </DialogTitle>
            <DialogDescription className="sr-only">
              Workspace chat interface for communicating with team members and group channels.
            </DialogDescription>
          </div>
        </DialogHeader>

        {/* Workspace Tabs */}
        <Tabs 
          value={activeTab} 
          onValueChange={(val) => {
            setActiveTab(val);
            if (val === 'org') {
              setActiveKey('org');
            }
          }}
          className="w-full flex-1 flex flex-col min-h-0"
        >
          <TabsList className="grid grid-cols-3 bg-zinc-100/50 dark:bg-zinc-900/40 rounded-xl p-1 border border-zinc-200/30 dark:border-zinc-800/30">
            <TabsTrigger
              value="direct"
              className="text-xs font-semibold py-2 rounded-lg gap-1.5 transition-all cursor-pointer data-state=active:bg-white data-state=active:dark:bg-zinc-950 data-state=active:shadow-sm"
            >
              <MessageSquare size={13} />
              Direct
            </TabsTrigger>
            <TabsTrigger
              value="groups"
              className="text-xs font-semibold py-2 rounded-lg gap-1.5 transition-all cursor-pointer data-state=active:bg-white data-state=active:dark:bg-zinc-950 data-state=active:shadow-sm"
            >
              <Users size={13} />
              Groups
            </TabsTrigger>
            <TabsTrigger
              value="org"
              className="text-xs font-semibold py-2 rounded-lg gap-1.5 transition-all cursor-pointer data-state=active:bg-white data-state=active:dark:bg-zinc-950 data-state=active:shadow-sm"
            >
              <Radio size={13} />
              Org Broadcast
            </TabsTrigger>
          </TabsList>

          <TabsContent value="direct" className="flex-1 min-h-0 focus-visible:outline-none">
            <DirectTab
              currentUserId={currentUserId}
              onSendMessage={(recipientId, text, msgType, customerReqData) =>
                onSendWSMessage(recipientId, text, 'direct', msgType, customerReqData)
              }
              isActive={activeTab === 'direct'}
            />
          </TabsContent>

          <TabsContent value="groups" className="flex-1 min-h-0 focus-visible:outline-none">
            <GroupsTab
              currentUserId={currentUserId}
              onSendMessage={(groupId, text) =>
                onSendWSMessage(groupId, text, 'group')
              }
              isActive={activeTab === 'groups'}
            />
          </TabsContent>

          <TabsContent value="org" className="flex-1 min-h-0 focus-visible:outline-none">
            <OrgTab
              currentUserId={currentUserId}
              currentUserRole={currentUserRole}
              onSendMessage={(convoId, text) =>
                onSendWSMessage(convoId, text, 'org')
              }
            />
          </TabsContent>
        </Tabs>
      </DialogContent>
    </Dialog>
  );
};
