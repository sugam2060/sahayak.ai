'use client';

import React, { useRef, useEffect, useState } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Send, Lock } from 'lucide-react';
import { InternalMessage } from '@/types/internal-chat';

interface ChatPaneProps {
  messages: InternalMessage[];
  onSendMessage: (text: string) => void;
  currentUserId: string;
  placeholder?: string;
  readOnly?: boolean;
  readOnlyMessage?: string;
  extraActions?: React.ReactNode;
  renderMessage?: (msg: InternalMessage) => React.ReactNode;
}

export const ChatPane: React.FC<ChatPaneProps> = ({
  messages,
  onSendMessage,
  currentUserId,
  placeholder = 'Type a message...',
  readOnly = false,
  readOnlyMessage = 'This channel is read-only.',
  extraActions,
  renderMessage,
}) => {
  const [inputText, setInputText] = useState('');
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!inputText.trim() || readOnly) return;
    onSendMessage(inputText);
    setInputText('');
  };

  return (
    <div className="flex flex-col h-[400px] bg-white/40 dark:bg-zinc-950/40 rounded-xl overflow-hidden border border-zinc-200/50 dark:border-zinc-800/50 backdrop-blur-md">
      {/* Messages Feed */}
      <div className="flex-1 overflow-y-auto p-4 space-y-3 min-h-0">
        {messages.length === 0 ? (
          <div className="h-full flex items-center justify-center text-zinc-400 dark:text-zinc-500 text-xs">
            No messages yet. Say hello!
          </div>
        ) : (
          messages.map((msg) => {
            const isMe = String(msg.sender_id) === String(currentUserId);
            
            // Allow custom rendering of join requests, etc.
            if (renderMessage) {
              const customRender = renderMessage(msg);
              if (customRender) return customRender;
            }

            return (
              <div
                key={msg.message_id}
                className={`flex flex-col ${isMe ? 'items-end' : 'items-start'}`}
              >
                <span className="text-[10px] text-zinc-500 mb-0.5 px-1 font-medium">
                  {msg.sender_name}
                </span>
                <div
                  className={`max-w-[75%] px-3 py-2 rounded-2xl text-sm leading-relaxed ${
                    isMe
                      ? 'bg-gradient-to-br from-[#7C63D4] to-[#5E9EEB] text-white rounded-tr-none shadow-sm'
                      : 'bg-white/80 dark:bg-zinc-900/80 border border-zinc-200/50 dark:border-zinc-850 text-zinc-900 dark:text-zinc-100 rounded-tl-none shadow-xs'
                  }`}
                >
                  {msg.text}
                </div>
                <span className="text-[9px] text-zinc-400 mt-0.5 px-1">
                  {new Date(msg.created_at).toLocaleTimeString([], {
                    hour: '2-digit',
                    minute: '2-digit',
                  })}
                </span>
              </div>
            );
          })
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Actions and Message Input */}
      <div className="border-t border-zinc-200/50 dark:border-zinc-800/50 bg-white/20 dark:bg-zinc-950/20 p-2 space-y-2">
        {extraActions && <div className="flex items-center gap-2 px-1">{extraActions}</div>}

        {readOnly ? (
          <div className="flex items-center justify-center gap-2 py-2 text-xs text-zinc-500 dark:text-zinc-400 font-semibold bg-zinc-100/50 dark:bg-zinc-900/50 rounded-lg border border-dashed border-zinc-200 dark:border-zinc-800">
            <Lock size={12} className="text-zinc-400" />
            {readOnlyMessage}
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="flex gap-2 items-center">
            <Input
              value={inputText}
              onChange={(e) => setInputText(e.target.value)}
              placeholder={placeholder}
              className="flex-1 bg-white/80 dark:bg-zinc-900/80 border border-zinc-200/50 dark:border-zinc-800/50 rounded-xl focus-visible:ring-1 focus-visible:ring-[#7C63D4]"
            />
            <Button
              type="submit"
              size="icon"
              disabled={!inputText.trim()}
              className="rounded-xl bg-gradient-to-br from-[#7C63D4] to-[#5E9EEB] hover:opacity-90 text-white cursor-pointer"
            >
              <Send size={14} />
            </Button>
          </form>
        )}
      </div>
    </div>
  );
};
