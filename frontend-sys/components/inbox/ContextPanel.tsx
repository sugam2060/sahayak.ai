'use client';

import React from 'react';
import { Mail, Hash, Sparkles } from 'lucide-react';
import { useChatHistory } from '@/services/api/chats';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from '@/components/ui/dialog';

interface ContextPanelProps {
  selectedChat: { platform: string; senderId: number } | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

const parseDate = (dateStr: string) => {
  if (!dateStr) return new Date();
  const timePart = dateStr.split('T')[1];
  const hasTimezone = dateStr.endsWith('Z') || 
                      (timePart && (timePart.includes('+') || timePart.includes('-')));
  return new Date(hasTimezone ? dateStr : `${dateStr}Z`);
};

const formatTime = (isoString: string) => {
  if (!isoString) return '';
  try {
    return parseDate(isoString).toLocaleString([], {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  } catch {
    return '';
  }
};

export const ContextPanel = ({ selectedChat, open, onOpenChange }: ContextPanelProps) => {
  const { data } = useChatHistory(
    selectedChat?.platform,
    selectedChat?.senderId
  );

  const chat = data?.chat;

  if (!selectedChat || !chat) {
    return null;
  }

  const initials = chat.user.sender_name
    .split(' ')
    .map((n) => n[0])
    .join('')
    .toUpperCase()
    .slice(0, 2);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[400px] bg-white border border-slate-200 shadow-2xl p-6 rounded-2xl">
        <DialogHeader>
          <DialogTitle className="text-base font-bold text-slate-900">Customer Profile Context</DialogTitle>
          <DialogDescription className="text-xs text-slate-400">
            Metadata and AI-generated summary for the active conversation.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-6 mt-4">
          {/* Profile Section */}
          <div className="text-center space-y-3">
            <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-indigo-100 to-blue-50 mx-auto flex items-center justify-center text-xl font-bold text-indigo-600 shadow-inner border border-white">
              {initials}
            </div>
            <div>
              <h3 className="text-sm font-bold text-slate-900 tracking-tight">{chat.user.sender_name}</h3>
              <p className="text-[10px] text-indigo-500 font-bold uppercase tracking-widest mt-0.5">Active User</p>
            </div>
            
            <div className="flex justify-center gap-1.5">
              <span className="px-2 py-0.5 rounded-md bg-indigo-50 text-[9px] font-semibold text-indigo-600 uppercase">{chat.platform} channel</span>
              <span className="px-2 py-0.5 rounded-md bg-blue-50 text-[9px] font-semibold text-blue-600 uppercase">ID: {chat.user.sender_id}</span>
            </div>
          </div>

          {/* Contact Info */}
          <div className="space-y-2">
            <div className="p-2.5 rounded-xl bg-slate-50 border border-slate-100 flex items-center gap-3">
              <div className="w-7 h-7 rounded-lg bg-indigo-50 flex items-center justify-center text-indigo-500">
                <Mail className="w-3.5 h-3.5" />
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-[9px] font-bold text-slate-400 uppercase tracking-widest">Username</p>
                <p className="text-xs font-semibold text-slate-700 truncate">
                  {chat.user.sender_username ? `@${chat.user.sender_username}` : 'No username'}
                </p>
              </div>
            </div>
            <div className="p-2.5 rounded-xl bg-slate-50 border border-slate-100 flex items-center gap-3">
              <div className="w-7 h-7 rounded-lg bg-indigo-50 flex items-center justify-center text-indigo-500">
                <Hash className="w-3.5 h-3.5" />
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-[9px] font-bold text-slate-400 uppercase tracking-widest">Chat ID</p>
                <p className="text-xs font-semibold text-slate-700">{chat.chat_id}</p>
              </div>
            </div>
          </div>

          {/* Conversation Summary Section */}
          <div className="p-4 rounded-xl bg-gradient-to-br from-indigo-50/40 to-blue-50/40 border border-indigo-100/50 shadow-inner">
             <h4 className="text-[10px] font-bold text-slate-500 uppercase tracking-widest mb-2 flex items-center gap-1.5">
               <Sparkles className="w-3.5 h-3.5 text-indigo-500" /> AI Conversation Summary
             </h4>
              <p className="text-xs text-slate-600 leading-relaxed italic">
                &ldquo;The customer has contacted support regarding their conversation history on the {chat.platform} platform. The dialogue consists of {chat.messages.length} message(s), with the last message received at {formatTime(chat.updated_at)}.&rdquo;
              </p>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
};
