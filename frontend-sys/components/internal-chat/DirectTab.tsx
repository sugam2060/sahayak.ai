'use client';

import React, { useState } from 'react';
import { useInternalMembers, useDirectHistory, useRespondCustomerRequest } from '@/services/api/internal-chats';
import { useChats, useRespondHandoff } from '@/services/api/chats';
import { ChatPane } from './ChatPane';
import { InternalMessage, InternalMember } from '@/types/internal-chat';
import { Button } from '@/components/ui/button';
import { ChevronRight, Key, Check, X, ShieldAlert, ArrowRightLeft, Clock, CheckCircle, XCircle, AlertTriangle } from 'lucide-react';
import { toast } from 'sonner';

interface DirectTabProps {
  currentUserId: string;
  onSendMessage: (recipientId: string, text: string, msgType?: 'text' | 'customer_chat_request', customerReqData?: unknown) => void;
}

export const DirectTab: React.FC<DirectTabProps> = ({ currentUserId, onSendMessage }) => {
  const [selectedMember, setSelectedMember] = useState<InternalMember | null>(null);
  const [showRequestDialog, setShowRequestDialog] = useState(false);

  // Queries
  const { data: membersData, isLoading: loadingMembers } = useInternalMembers();
  const { data: historyData, isLoading: loadingHistory } = useDirectHistory(selectedMember?.user_id || null);
  const { data: chatsData } = useChats();

  const respondMutation = useRespondCustomerRequest();
  const handoffRespondMutation = useRespondHandoff();

  const handleSendRequest = (platform: string, senderId: string, customerName: string) => {
    if (!selectedMember) return;
    
    onSendMessage(
      selectedMember.user_id,
      `Requested to join customer chat with ${customerName} on ${platform}`,
      'customer_chat_request',
      { platform, sender_id: senderId }
    );
    setShowRequestDialog(false);
    toast.success('Access request sent successfully!');
  };

  const handleRespond = async (messageId: string, action: 'accept' | 'decline') => {
    try {
      await respondMutation.mutateAsync({ message_id: messageId, action });
      toast.success(`Request ${action}ed successfully.`);
    } catch (err: unknown) {
      toast.error((err as Error).message || 'Failed to respond to request.');
    }
  };

  const renderMessage = (msg: InternalMessage) => {
    // Handle handoff_request messages
    if (msg.message_type === 'handoff_request') {
      const hr = msg.handoff_request;
      if (!hr) return null;

      const isMe = String(msg.sender_id) === String(currentUserId);
      const statusColors: Record<string, string> = {
        pending: 'bg-amber-100 text-amber-800 dark:bg-amber-900/20 dark:text-amber-400',
        granted: 'bg-emerald-100 text-emerald-800 dark:bg-emerald-900/20 dark:text-emerald-400',
        declined: 'bg-red-100 text-red-800 dark:bg-red-900/20 dark:text-red-400',
        expired: 'bg-zinc-100 text-zinc-600 dark:bg-zinc-800/20 dark:text-zinc-400',
      };
      const statusIcons: Record<string, React.ReactNode> = {
        pending: <Clock size={12} className="text-amber-600" />,
        granted: <CheckCircle size={12} className="text-emerald-600" />,
        declined: <XCircle size={12} className="text-red-600" />,
        expired: <AlertTriangle size={12} className="text-zinc-500" />,
      };

      return (
        <div key={msg.message_id} className={`flex flex-col ${isMe ? 'items-end' : 'items-start'}`}>
          <span className="text-[10px] text-zinc-500 mb-0.5 px-1 font-medium">{msg.sender_name}</span>
          <div className={`border rounded-2xl p-4 max-w-[85%] text-sm space-y-3 shadow-md ${
            isMe
              ? 'bg-amber-50/80 border-amber-200/50 rounded-tr-none'
              : 'bg-white/95 dark:bg-zinc-900/95 border-amber-200/50 dark:border-zinc-800 rounded-tl-none'
          }`}>
            <div className="flex items-center gap-2 font-semibold text-amber-700 text-xs uppercase tracking-wide">
              <ArrowRightLeft size={14} />
              Chat Handoff Request
            </div>
            <p className="text-zinc-600 dark:text-zinc-400 text-xs">
              {isMe
                ? 'You requested to take over a customer conversation.'
                : `${msg.sender_name} wants to take over a customer conversation you are handling.`}
            </p>

            <div className="flex items-center gap-1.5">
              {statusIcons[hr.status] || null}
              <span className={`text-[10px] font-bold uppercase px-1.5 py-0.5 rounded-full ${statusColors[hr.status] || 'bg-zinc-100 text-zinc-600'}`}>
                {hr.status}
              </span>
            </div>

            {/* Show Accept/Decline only for the handler and only when pending */}
            {!isMe && hr.status === 'pending' && (
              <div className="flex gap-2 justify-end pt-1">
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => {
                    handoffRespondMutation.mutate({ handoff_id: hr.id, action: 'decline' }, {
                      onSuccess: () => toast.success('Handoff declined.'),
                      onError: (err: Error) => toast.error(err.message || 'Failed to decline handoff.'),
                    });
                  }}
                  disabled={handoffRespondMutation.isPending}
                  className="h-8 px-3 rounded-lg border-zinc-200 dark:border-zinc-800 text-xs gap-1 hover:bg-red-50 hover:text-red-600 cursor-pointer"
                >
                  <X size={12} />
                  Decline
                </Button>
                <Button
                  size="sm"
                  onClick={() => {
                    handoffRespondMutation.mutate({ handoff_id: hr.id, action: 'grant' }, {
                      onSuccess: () => toast.success('Handoff accepted! Lock transferred.'),
                      onError: (err: Error) => toast.error(err.message || 'Failed to accept handoff.'),
                    });
                  }}
                  disabled={handoffRespondMutation.isPending}
                  className="h-8 px-3 rounded-lg bg-gradient-to-br from-amber-500 to-orange-500 text-white text-xs gap-1 hover:opacity-90 cursor-pointer"
                >
                  <Check size={12} />
                  Accept
                </Button>
              </div>
            )}
          </div>
          <span className="text-[9px] text-zinc-400 mt-0.5 px-1">
            {new Date(msg.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
          </span>
        </div>
      );
    }

    if (msg.message_type !== 'customer_chat_request') return null;

    const req = msg.customer_chat_request;
    if (!req) return null;

    const isMe = String(msg.sender_id) === String(currentUserId);

    if (isMe) {
      // Sent by me
      return (
        <div key={msg.message_id} className="flex flex-col items-end">
          <span className="text-[10px] text-zinc-500 mb-0.5 px-1 font-medium">{msg.sender_name}</span>
          <div className="bg-[#7C63D4]/20 border border-[#7C63D4]/30 rounded-2xl rounded-tr-none px-4 py-3 max-w-[80%] text-sm space-y-2 text-zinc-800 dark:text-zinc-200">
            <div className="flex items-center gap-2 font-semibold text-primary text-xs uppercase tracking-wide">
              <ShieldAlert size={14} className="text-[#7C63D4]" />
              Access Request Sent
            </div>
            <p className="text-zinc-600 dark:text-zinc-400 text-xs">
              You requested read/write access to customer conversation:
            </p>
            <div className="bg-white/50 dark:bg-zinc-900/50 p-2 rounded-lg border border-zinc-200/20 text-xs">
              <span className="font-semibold capitalize">{req.platform}</span>: {req.sender_id}
            </div>
            <div className="flex items-center gap-1.5 justify-end">
              <span className="text-[10px] font-bold uppercase tracking-wider text-zinc-400">Status:</span>
              <span className={`text-[10px] font-bold uppercase px-1.5 py-0.5 rounded-full ${
                req.status === 'pending'
                  ? 'bg-amber-100 text-amber-800 dark:bg-amber-900/20 dark:text-amber-400'
                  : req.status === 'accepted'
                  ? 'bg-emerald-100 text-emerald-800 dark:bg-emerald-900/20 dark:text-emerald-400'
                  : 'bg-red-100 text-red-800 dark:bg-red-900/20 dark:text-red-400'
              }`}>
                {req.status}
              </span>
            </div>
          </div>
          <span className="text-[9px] text-zinc-400 mt-0.5 px-1">
            {new Date(msg.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
          </span>
        </div>
      );
    } else {
      // Received from other user
      return (
        <div key={msg.message_id} className="flex flex-col items-start">
          <span className="text-[10px] text-zinc-500 mb-0.5 px-1 font-medium">{msg.sender_name}</span>
          <div className="bg-white/95 dark:bg-zinc-900/95 border border-zinc-200/50 dark:border-zinc-800 rounded-2xl rounded-tl-none p-4 max-w-[80%] text-sm space-y-3 shadow-md">
            <div className="flex items-center gap-2 font-semibold text-[#7C63D4] text-xs uppercase tracking-wide">
              <Key size={14} />
              Access Request Received
            </div>
            <p className="text-zinc-600 dark:text-zinc-400 text-xs">
              {msg.sender_name} is requesting read/write access to unlock your conversation:
            </p>
            <div className="bg-zinc-100/80 dark:bg-zinc-950/80 p-2 rounded-lg border border-zinc-200/20 text-xs font-mono">
              <span className="font-semibold capitalize text-primary">{req.platform}</span>: {req.sender_id}
            </div>

            {req.status === 'pending' ? (
              <div className="flex gap-2 justify-end pt-1">
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => handleRespond(msg.message_id, 'decline')}
                  className="h-8 px-3 rounded-lg border-zinc-200 dark:border-zinc-800 text-xs gap-1 hover:bg-red-50 hover:text-red-600 dark:hover:bg-red-950/20 cursor-pointer"
                >
                  <X size={12} />
                  Decline
                </Button>
                <Button
                  size="sm"
                  onClick={() => handleRespond(msg.message_id, 'accept')}
                  className="h-8 px-3 rounded-lg bg-gradient-to-br from-[#7C63D4] to-[#5E9EEB] text-white text-xs gap-1 hover:opacity-90 cursor-pointer"
                >
                  <Check size={12} />
                  Accept
                </Button>
              </div>
            ) : (
              <div className="flex items-center gap-1.5 justify-end">
                <span className="text-[10px] font-bold uppercase tracking-wider text-zinc-400">Response:</span>
                <span className={`text-[10px] font-bold uppercase px-1.5 py-0.5 rounded-full ${
                  req.status === 'accepted'
                    ? 'bg-emerald-100 text-emerald-800 dark:bg-emerald-900/20 dark:text-emerald-400'
                    : 'bg-red-100 text-red-800 dark:bg-red-900/20 dark:text-red-400'
                }`}>
                  {req.status}
                </span>
              </div>
            )}
          </div>
          <span className="text-[9px] text-zinc-400 mt-0.5 px-1">
            {new Date(msg.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
          </span>
        </div>
      );
    }
  };

  // Filter customer chats currently locked by the selected target user
  const lockableCustomerChats = (chatsData?.chats || []).filter(
    (c) => c.bot_id !== null && c.bot_id !== 'ai' && c.bot_id === selectedMember?.user_id
  );

  return (
    <div className="grid grid-cols-5 gap-4 h-[440px] pt-1">
      {/* Members list */}
      <div className="col-span-2 border-r border-zinc-200/50 dark:border-zinc-800/50 pr-2 overflow-y-auto flex flex-col gap-1.5">
        <h3 className="text-xs font-bold text-zinc-400 dark:text-zinc-500 uppercase tracking-wider mb-1 px-1">
          Team Members
        </h3>
        {loadingMembers ? (
          <div className="flex justify-center items-center py-8">
            <div className="w-5 h-5 border-2 border-[#7C63D4] border-t-transparent rounded-full animate-spin" />
          </div>
        ) : (membersData?.members || []).length === 0 ? (
          <div className="text-xs text-zinc-400 py-4 text-center">No other members online.</div>
        ) : (
          (membersData?.members || []).map((m) => (
            <button
              key={m.user_id}
              onClick={() => setSelectedMember(m)}
              className={`w-full flex items-center justify-between p-2 rounded-xl text-left text-xs transition-all border cursor-pointer ${
                selectedMember?.user_id === m.user_id
                  ? 'bg-zinc-100 dark:bg-zinc-900/50 border-zinc-200/60 dark:border-zinc-800 text-zinc-900 dark:text-zinc-100 font-medium'
                  : 'bg-transparent border-transparent hover:bg-zinc-50 dark:hover:bg-zinc-900/20 text-zinc-600 dark:text-zinc-400'
              }`}
            >
              <div className="flex flex-col min-w-0 pr-1">
                <span className="font-semibold truncate">{m.full_name}</span>
                <span className="text-[10px] text-zinc-400 capitalize truncate">{m.role.toLowerCase()}</span>
              </div>
              <ChevronRight size={14} className="text-zinc-400" />
            </button>
          ))
        )}
      </div>

      {/* Direct conversation window */}
      <div className="col-span-3 flex flex-col h-full min-w-0 justify-center">
        {selectedMember ? (
          <div className="flex flex-col h-full min-w-0">
            {/* Header */}
            <div className="flex items-center justify-between pb-2 border-b border-zinc-200/50 dark:border-zinc-800/50 mb-2">
              <div className="min-w-0">
                <h4 className="text-sm font-bold text-zinc-900 dark:text-zinc-100 truncate">{selectedMember.full_name}</h4>
                <p className="text-[10px] text-zinc-400 capitalize truncate">{selectedMember.role.toLowerCase()}</p>
              </div>
              
              {/* Join customer thread trigger */}
              <Button
                size="sm"
                variant="outline"
                onClick={() => setShowRequestDialog(!showRequestDialog)}
                className="h-8 px-2.5 rounded-lg border-zinc-200 dark:border-zinc-800 text-xs gap-1 hover:bg-[#7C63D4]/10 hover:text-[#7C63D4] cursor-pointer"
              >
                <Key size={12} />
                Request Chat
              </Button>
            </div>

            {/* Chat Pane */}
            {loadingHistory ? (
              <div className="flex-1 flex justify-center items-center">
                <div className="w-8 h-8 border-2 border-[#7C63D4] border-t-transparent rounded-full animate-spin" />
              </div>
            ) : (
              <ChatPane
                messages={historyData?.conversation?.messages || []}
                onSendMessage={(text) => onSendMessage(selectedMember.user_id, text, 'text')}
                currentUserId={currentUserId}
                placeholder={`Message ${selectedMember.full_name}...`}
                renderMessage={renderMessage}
                extraActions={
                  showRequestDialog ? (
                    <div className="w-full bg-zinc-50 dark:bg-zinc-900/50 border border-zinc-200 dark:border-zinc-800 p-2.5 rounded-xl text-left space-y-2 mt-1 z-10 shadow-lg animate-in fade-in-0 slide-in-from-bottom-2">
                      <div className="flex items-center justify-between">
                        <span className="text-[10px] font-bold text-zinc-500 uppercase tracking-wide">
                          Select Customer Lock to Request
                        </span>
                        <Button
                          size="icon-sm"
                          variant="ghost"
                          onClick={() => setShowRequestDialog(false)}
                          className="h-4 w-4 text-zinc-400 hover:text-zinc-600 rounded-full"
                        >
                          <X size={10} />
                        </Button>
                      </div>
                      
                      {lockableCustomerChats.length === 0 ? (
                        <p className="text-[10px] text-zinc-400 text-center py-2">
                          No active locked customer chats available to request.
                        </p>
                      ) : (
                        <div className="max-h-24 overflow-y-auto space-y-1 pr-1">
                          {lockableCustomerChats.map((c) => (
                            <button
                              key={c.user.sender_id}
                              onClick={() =>
                                handleSendRequest(c.platform, String(c.user.sender_id), c.user.sender_name)
                              }
                              className="w-full text-left p-1.5 rounded-md hover:bg-[#7C63D4]/10 hover:text-[#7C63D4] text-[10px] flex items-center justify-between border border-transparent hover:border-zinc-200 dark:hover:border-zinc-800 transition-colors cursor-pointer"
                            >
                              <div className="flex flex-col">
                                <span className="font-semibold text-zinc-800 dark:text-zinc-200">
                                  {c.user.sender_name}
                                </span>
                                <span className="text-[8px] text-zinc-400 capitalize">
                                  {c.platform} ({c.user.sender_id})
                                </span>
                              </div>
                              <span className="text-[8px] px-1 py-0.2 bg-zinc-100 dark:bg-zinc-800 rounded font-semibold text-zinc-500 capitalize">
                                Locked by: {c.locker_name || 'AI'}
                              </span>
                            </button>
                          ))}
                        </div>
                      )}
                    </div>
                  ) : null
                }
              />
            )}
          </div>
        ) : (
          <div className="h-full flex items-center justify-center text-zinc-400 dark:text-zinc-500 text-xs bg-zinc-50/20 dark:bg-zinc-900/10 border border-dashed border-zinc-200 dark:border-zinc-800 rounded-xl p-6 text-center">
            Select a team member to start direct messaging.
          </div>
        )}
      </div>
    </div>
  );
};
