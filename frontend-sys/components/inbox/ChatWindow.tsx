'use client';

import React, { useEffect, useRef, useState } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import * as z from 'zod';
import { Plus, MoreHorizontal, Paperclip, ImageIcon, Package, ShoppingBag, Sparkles, Send, CheckCircle2, Smile, Menu } from 'lucide-react';
import { FaTelegram, FaInstagram, FaTwitter } from 'react-icons/fa';
import { useChatHistory, useSendReply } from '@/services/api/chats';
import { ContextPanel } from './ContextPanel';
import { useAuthStore } from '@/store/authStore';
import dynamic from 'next/dynamic';

const EmojiPicker = dynamic(
  () => import('emoji-picker-react').then((mod) => mod.default),
  { ssr: false }
);

interface ChatWindowProps {
  selectedChat: { platform: string; senderId: number } | null;
  onMenuClick?: () => void;
}

const formSchema = z.object({
  text: z.string().min(1, 'Message content cannot be empty.'),
});

type FormData = z.infer<typeof formSchema>;

const parseDate = (dateStr: string) => {
  if (!dateStr) return new Date();
  const timePart = dateStr.split('T')[1];
  const hasTimezone = dateStr.endsWith('Z') || 
                      (timePart && (timePart.includes('+') || timePart.includes('-')));
  return new Date(hasTimezone ? dateStr : `${dateStr}Z`);
};

export const ChatWindow = ({ selectedChat, onMenuClick }: ChatWindowProps) => {
  const { data, isLoading, error } = useChatHistory(
    selectedChat?.platform,
    selectedChat?.senderId
  );
  
  const { user } = useAuthStore();
  const sendReplyMutation = useSendReply();
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const [showActions, setShowActions] = useState(false);
  const [isContextOpen, setIsContextOpen] = useState(false);
  const [showMenu, setShowMenu] = useState(false);
  const [showEmojiPicker, setShowEmojiPicker] = useState(false);
  
  const {
    register,
    handleSubmit,
    reset,
    setValue,
    getValues,
    formState: { errors },
  } = useForm<FormData>({
    resolver: zodResolver(formSchema),
    defaultValues: { text: '' },
  });

  const chat = data?.chat;
  const messages = chat?.messages || [];

  // Scroll to bottom on new messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages.length]);

  // Handle Enter submission (Shift+Enter for newlines)
  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(onSubmit)();
    }
  };

  const onSubmit = async (formData: FormData) => {
    if (!selectedChat) return;
    try {
      await sendReplyMutation.mutateAsync({
        sender_id: selectedChat.senderId,
        platform: selectedChat.platform,
        text: formData.text,
      });
      reset();
    } catch (err) {
      console.error('Failed to send reply:', err);
    }
  };

  if (!selectedChat) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center bg-white/50 backdrop-blur-sm relative overflow-hidden p-8 text-center text-slate-500">
        <div className="w-16 h-16 rounded-3xl bg-indigo-50 border border-indigo-100 flex items-center justify-center text-indigo-500 mb-4 animate-bounce">
          <Sparkles className="w-8 h-8" />
        </div>
        <h3 className="text-base font-bold text-slate-800">No Chat Selected</h3>
        <p className="text-xs text-slate-400 max-w-xs mt-1">
          Select a customer conversation from the list to view history and send replies.
        </p>
        <button 
          onClick={onMenuClick}
          className="mt-6 px-4 py-2.5 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-xs font-semibold cursor-pointer md:hidden flex items-center gap-2 shadow-sm transition-all"
        >
          <Menu className="w-4 h-4" />
          View Conversations
        </button>
      </div>
    );
  }

  const initials = chat?.user.sender_name
    .split(' ')
    .map((n) => n[0])
    .join('')
    .toUpperCase()
    .slice(0, 2) || '??';

  const orgInitials = user?.organization_name
    ? user.organization_name
        .split(' ')
        .map((n) => n[0])
        .join('')
        .toUpperCase()
        .slice(0, 2)
    : 'YO';

  return (
    <div className="flex-1 flex flex-col bg-white/50 backdrop-blur-sm relative overflow-hidden">
      {/* Header */}
      <div className="h-16 flex items-center justify-between px-6 border-b border-indigo-100/50 bg-white/80 backdrop-blur-md z-10">
        <div className="flex items-center gap-3">
          {/* Hamburger menu button on mobile */}
          <button 
            onClick={onMenuClick}
            className="p-2 -ml-2 text-slate-500 hover:text-slate-800 hover:bg-slate-100 rounded-lg md:hidden cursor-pointer"
            aria-label="Open Sidebar"
          >
            <Menu className="w-5 h-5" />
          </button>
          
          <div className="w-10 h-10 rounded-full bg-indigo-100 flex items-center justify-center text-indigo-600 font-bold border border-white">
            {initials}
          </div>
          <div 
            onClick={() => setIsContextOpen(true)}
            className="cursor-pointer select-none group/hdr"
          >
            <div className="flex items-center gap-2">
              <h3 className="text-sm font-bold text-slate-900 group-hover/hdr:underline">{chat?.user.sender_name}</h3>
              <span className="px-2 py-0.5 rounded-full bg-indigo-50 text-[10px] font-bold text-indigo-600 uppercase flex items-center gap-1">
                {selectedChat.platform === 'telegram' && <FaTelegram className="w-3.5 h-3.5 text-blue-500" />}
                {selectedChat.platform === 'instagram' && <FaInstagram className="w-3.5 h-3.5 text-pink-600" />}
                {selectedChat.platform === 'twitter' && <FaTwitter className="w-3.5 h-3.5 text-blue-400" />}
                {selectedChat.platform} DM
              </span>
            </div>
            <p className="text-[10px] text-slate-400 font-medium">
              {chat?.user.sender_username ? `@${chat.user.sender_username}` : 'No username'}
            </p>
          </div>
        </div>
        
        <div className="flex items-center gap-3 relative">
          <button 
            type="button" 
            onClick={() => setShowMenu(!showMenu)}
            className={`p-2 rounded-lg transition-colors cursor-pointer ${showMenu ? 'bg-slate-100 text-slate-600' : 'text-slate-400 hover:text-slate-600'}`}
          >
            <MoreHorizontal className="w-5 h-5" />
          </button>

          {showMenu && (
            <div className="absolute right-0 top-10 bg-white border border-indigo-50 rounded-xl p-1.5 shadow-xl flex flex-col gap-0.5 z-20 min-w-[120px] animate-in fade-in slide-in-from-top-1 duration-150">
              <button 
                type="button" 
                onClick={() => {
                  console.log("Assign clicked");
                  setShowMenu(false);
                }} 
                className="flex items-center w-full px-3 py-2 text-left hover:bg-indigo-50/50 rounded-lg text-slate-600 text-xs font-semibold cursor-pointer"
              >
                <span>Assign Ticket</span>
              </button>
              <button 
                type="button" 
                onClick={() => {
                  console.log("Resolve clicked");
                  setShowMenu(false);
                }} 
                className="flex items-center w-full px-3 py-2 text-left hover:bg-teal-50/50 rounded-lg text-teal-600 text-xs font-semibold cursor-pointer"
              >
                <span>Resolve Ticket</span>
              </button>
            </div>
          )}
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-6 space-y-6">
        {isLoading && (
          <div className="h-full flex items-center justify-center text-slate-500">
            <div className="w-8 h-8 border-2 border-indigo-600 border-t-transparent rounded-full animate-spin mb-2" />
            <span className="text-xs ml-2">Loading conversation history...</span>
          </div>
        )}

        {error && (
          <div className="p-4 text-center text-xs text-rose-500">
            Failed to load messages: {(error as any).message}
          </div>
        )}

        {!isLoading && !error && messages.length === 0 && (
          <div className="h-full flex flex-col items-center justify-center text-slate-400">
            <span className="text-xs">No messages yet. Send a reply to start.</span>
          </div>
        )}

        {!isLoading && !error && messages.map((msg) => {
          const isInbound = msg.direction === 'inbound';
          const msgTime = parseDate(msg.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

          return (
            <div 
              key={msg.message_id}
              className={`flex gap-3 max-w-[75%] ${isInbound ? '' : 'flex-row-reverse ml-auto'}`}
            >
              <div className={`w-8 h-8 rounded-full flex-shrink-0 flex items-center justify-center text-[10px] font-bold border border-white
                ${isInbound ? 'bg-indigo-100 text-indigo-600' : 'bg-indigo-600 text-white shadow-lg'}`}
              >
                {isInbound ? initials : orgInitials}
              </div>
              <div className={`space-y-1 ${isInbound ? '' : 'items-end flex flex-col'}`}>
                <div className={`p-4 rounded-2xl shadow-sm text-sm leading-relaxed
                  ${isInbound 
                    ? 'bg-white/80 backdrop-blur-md border border-indigo-50 rounded-tl-none text-slate-700' 
                    : 'bg-indigo-50 border border-indigo-200 rounded-tr-none text-slate-800'}`}
                >
                  {msg.text}
                </div>
                <div className="flex items-center gap-2 px-1">
                  <span className="text-[10px] font-medium text-slate-400">{msgTime}</span>
                  {!isInbound && <CheckCircle2 className="w-3 h-3 text-indigo-500" />}
                </div>
              </div>
            </div>
          );
        })}
        <div ref={messagesEndRef} />
      </div>

      {/* Reply Bar */}
      <form onSubmit={handleSubmit(onSubmit)} className="px-6 py-4 border-t border-indigo-100/50 bg-white/80 backdrop-blur-xl space-y-4 relative">
        {/* Actions Popup Menu */}
        {showActions && (
          <div className="absolute left-6 bottom-20 bg-white border border-indigo-50 rounded-2xl p-2 shadow-2xl flex flex-col gap-1 z-20 animate-in fade-in slide-in-from-bottom-2 duration-200">
            <button type="button" onClick={() => setShowActions(false)} className="flex items-center gap-3 px-4 py-2 hover:bg-indigo-50/50 rounded-xl text-slate-600 text-xs font-semibold cursor-pointer">
              <Paperclip className="w-4 h-4 text-indigo-500" />
              <span>Attach File</span>
            </button>
            <button type="button" onClick={() => setShowActions(false)} className="flex items-center gap-3 px-4 py-2 hover:bg-indigo-50/50 rounded-xl text-slate-600 text-xs font-semibold cursor-pointer">
              <ImageIcon className="w-4 h-4 text-pink-500" />
              <span>Upload Image</span>
            </button>
            <button type="button" onClick={() => setShowActions(false)} className="flex items-center gap-3 px-4 py-2 hover:bg-indigo-50/50 rounded-xl text-slate-600 text-xs font-semibold cursor-pointer">
              <Package className="w-4 h-4 text-amber-500" />
              <span>Add Product</span>
            </button>
            <button type="button" onClick={() => setShowActions(false)} className="flex items-center gap-3 px-4 py-2 hover:bg-indigo-50/50 rounded-xl text-slate-600 text-xs font-semibold cursor-pointer">
              <ShoppingBag className="w-4 h-4 text-teal-500" />
              <span>Create Order</span>
            </button>
          </div>
        )}

        {/* Emoji Picker Popup */}
        {showEmojiPicker && (
          <div className="absolute right-6 bottom-20 z-30 shadow-2xl rounded-2xl border border-slate-200 overflow-hidden">
            <EmojiPicker 
              onEmojiClick={(emojiData) => {
                const currentText = getValues('text') || '';
                setValue('text', currentText + emojiData.emoji);
                setShowEmojiPicker(false);
              }}
              height={350}
              width={300}
            />
          </div>
        )}

        <div className="flex items-center gap-3">
          {/* Add Actions Button */}
          <button 
            type="button" 
            onClick={() => setShowActions(!showActions)}
            className={`flex-shrink-0 h-[46px] w-[46px] rounded-xl flex items-center justify-center border transition-all cursor-pointer
              ${showActions ? 'bg-indigo-50 border-indigo-200 text-indigo-600' : 'bg-slate-50 border-slate-200 text-slate-400 hover:text-slate-600 hover:bg-slate-100'}`}
          >
            <Plus className={`w-5 h-5 transition-transform duration-200 ${showActions ? 'rotate-45' : ''}`} />
          </button>

          {/* Text Area Input */}
          <div className="flex-1 relative flex items-center">
            <textarea 
              placeholder={`Reply to ${chat?.user.sender_name || 'customer'}...`}
              {...register('text')}
              onKeyDown={handleKeyDown}
              disabled={sendReplyMutation.isPending}
              className="w-full bg-slate-100/50 border border-slate-200/80 rounded-xl pl-4 pr-20 py-3 text-sm focus:outline-none focus:border-indigo-600/30 transition-all resize-none min-h-[46px] max-h-40 placeholder:text-slate-400 leading-normal"
              rows={1}
              style={{ height: '46px' }}
            />
            {errors.text && (
              <p className="absolute left-0 -top-6 text-[10px] text-rose-500 px-2">{errors.text.message}</p>
            )}
            <div className="absolute right-3 flex items-center gap-1.5">
              <button 
                type="button" 
                onClick={() => setShowEmojiPicker(!showEmojiPicker)}
                className={`p-1 rounded text-slate-400 transition-colors cursor-pointer hover:text-indigo-500
                  ${showEmojiPicker ? 'text-indigo-600 bg-indigo-50' : ''}`}
              >
                <Smile className="w-4 h-4" />
              </button>
              <button type="button" className="p-1 rounded text-slate-400 hover:text-indigo-500 transition-all cursor-pointer">
                <Sparkles className="w-4 h-4" />
              </button>
            </div>
          </div>

          {/* Send Button */}
          <button 
            type="submit" 
            disabled={sendReplyMutation.isPending}
            className="h-[46px] w-[46px] flex-shrink-0 rounded-xl bg-indigo-600 flex items-center justify-center text-white shadow-md shadow-indigo-100 hover:bg-indigo-700 active:scale-95 transition-all cursor-pointer disabled:opacity-50"
          >
            {sendReplyMutation.isPending ? (
              <div className="w-5 h-5 border-2 border-white border-t-transparent rounded-full animate-spin" />
            ) : (
              <Send className="w-4 h-4" />
            )}
          </button>
        </div>

        {/* Footer info in the reply bar */}
        <div className="flex items-center justify-between mt-2 px-1 text-[9px] font-medium text-slate-400 uppercase tracking-wider font-mono">
          <span>Via: {selectedChat.platform} DM</span>
          <span>Press Enter to send, Shift + Enter for new line</span>
        </div>
      </form>

      {/* Context Panel Dialog */}
      <ContextPanel 
        selectedChat={selectedChat} 
        open={isContextOpen} 
        onOpenChange={setIsContextOpen} 
      />
    </div>
  );
};
