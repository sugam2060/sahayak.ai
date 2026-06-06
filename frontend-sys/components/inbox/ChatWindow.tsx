/* eslint-disable @next/next/no-img-element, @typescript-eslint/no-explicit-any */
'use client';

import React, { useEffect, useRef, useState } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import * as z from 'zod';
import { Plus, MoreHorizontal, ImageIcon, Package, ShoppingBag, Sparkles, Send, CheckCircle2, Smile, Menu, Ticket } from 'lucide-react';
import { FaTelegram, FaInstagram, FaTwitter, FaTiktok, FaWhatsapp, FaFacebookMessenger } from 'react-icons/fa';
import { useChatHistory, useSendReply, useToggleAI, useMarkChatAsRead } from '@/services/api/chats';
import { ContextPanel } from './ContextPanel';
import { useAuthStore } from '@/store/authStore';
import dynamic from 'next/dynamic';
import * as htmlToImage from 'html-to-image';
import { Product } from '@/types/product';
import { useQueryClient } from '@tanstack/react-query';
import { ProductShareModal } from './ProductShareModal';
import { CreateOrderModal } from './CreateOrderModal';
import { CreateTicketModal } from './CreateTicketModal';
import ReactMarkdown from 'react-markdown';

const EmojiPicker = dynamic(
  () => import('emoji-picker-react').then((mod) => mod.default),
  { ssr: false }
);

interface ChatWindowProps {
  selectedChat: { platform: string; senderId: string } | null;
  onMenuClick?: () => void;
}

const formSchema = z.object({
  text: z.string().min(1, 'Message content cannot be empty.'),
});

type FormData = z.infer<typeof formSchema>;

const renderMessageText = (text: string) => {
  if (!text) return null;
  return (
    <ReactMarkdown
      components={{
        p: ({ children }) => <p className="whitespace-pre-wrap mb-1 text-slate-700 dark:text-slate-300">{children}</p>,
        strong: ({ children }) => <strong className="font-bold text-slate-900 dark:text-white">{children}</strong>,
        em: ({ children }) => <em className="italic">{children}</em>,
        a: ({ href, children }) => (
          <a
            href={href}
            target="_blank"
            rel="noopener noreferrer"
            className="text-indigo-600 hover:text-indigo-800 underline font-semibold break-all"
          >
            {children}
          </a>
        ),
        ul: ({ children }) => <ul className="list-disc pl-5 my-1 space-y-0.5 text-slate-700 dark:text-slate-300">{children}</ul>,
        ol: ({ children }) => <ol className="list-decimal pl-5 my-1 space-y-0.5 text-slate-700 dark:text-slate-300">{children}</ol>,
        li: ({ children }) => <li className="my-0.5">{children}</li>,
        h1: ({ children }) => <h1 className="font-bold text-slate-900 dark:text-white text-lg my-2">{children}</h1>,
        h2: ({ children }) => <h2 className="font-bold text-slate-900 dark:text-white text-base my-2">{children}</h2>,
        h3: ({ children }) => <h3 className="font-bold text-slate-900 dark:text-white text-sm my-2">{children}</h3>,
        h4: ({ children }) => <h4 className="font-bold text-slate-900 dark:text-white text-xs my-2">{children}</h4>,
      }}
    >
      {text}
    </ReactMarkdown>
  );
};

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
  const toggleAIMutation = useToggleAI();
  const markReadMutation = useMarkChatAsRead();
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const queryClient = useQueryClient();

  const chat = data?.chat;
  const messages = chat?.messages || [];

  // Trigger mark read when chat is selected or new messages arrive
  useEffect(() => {
    if (selectedChat?.platform && selectedChat?.senderId && messages.length > 0) {
      const hasUnseen = messages.some((m: any) => m.direction === 'inbound' && !m.seen);
      if (hasUnseen) {
        markReadMutation.mutate({
          sender_id: selectedChat.senderId,
          platform: selectedChat.platform,
        });
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedChat?.platform, selectedChat?.senderId, messages.length]);

  // Product card sharing states
  const [isProductSelectorOpen, setIsProductSelectorOpen] = useState(false);
  const [selectedProductForCard, setSelectedProductForCard] = useState<Product | null>(null);
  const [isGeneratingCard, setIsGeneratingCard] = useState(false);
  const [isCreateOrderOpen, setIsCreateOrderOpen] = useState(false);
  const [isCreateTicketOpen, setIsCreateTicketOpen] = useState(false);
  const [cardLoadingProgress, setCardLoadingProgress] = useState('');
  const cardRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleImageUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (!files || files.length === 0 || !selectedChat) return;

    setIsGeneratingCard(true);
    setCardLoadingProgress(`Uploading ${files.length} image(s)...`);

    try {
      const formData = new FormData();
      formData.append('sender_id', selectedChat.senderId.toString());
      formData.append('platform', selectedChat.platform);
      
      for (let i = 0; i < files.length; i++) {
        formData.append('image_files', files[i]);
      }

      const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
      const response = await fetch(`${API_BASE_URL}/api/chats/reply-image`, {
        method: 'POST',
        credentials: 'include',
        body: formData,
      });

      if (!response.ok) {
        const errData = await response.json().catch(() => ({}));
        throw new Error(errData.detail || 'Failed to upload images.');
      }

      queryClient.invalidateQueries({
        queryKey: ['chat-history', selectedChat.platform, selectedChat.senderId],
      });
      queryClient.invalidateQueries({
        queryKey: ['chats'],
      });
    } catch (err) {
      console.error('Error uploading images:', err);
    } finally {
      setIsGeneratingCard(false);
      setCardLoadingProgress('');
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
    }
  };

  const handleSelectProduct = async (products: Product[]) => {
    if (!selectedChat || products.length === 0) return;
    setIsProductSelectorOpen(false);
    setIsGeneratingCard(true);

    try {
      const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
      
      for (let i = 0; i < products.length; i++) {
        const product = products[i];
        setCardLoadingProgress(`Preparing card ${i + 1} of ${products.length}: ${product.name}`);
        setSelectedProductForCard(product);

        // Wait brief duration for canvas/image layout stability
        await new Promise((resolve) => setTimeout(resolve, 400));

        const node = cardRef.current;
        if (!node) throw new Error('Card template node not found.');

        setCardLoadingProgress(`Rendering card ${i + 1} of ${products.length}...`);
        const dataUrl = await htmlToImage.toPng(node, {
          cacheBust: true,
          style: {
            transform: 'scale(1)',
          },
        });

        const blob = await (await fetch(dataUrl)).blob();
        const file = new File([blob], `${product.name.replace(/\s+/g, '_')}_card.png`, { type: 'image/png' });

        setCardLoadingProgress(`Uploading card ${i + 1} of ${products.length}...`);
        const formData = new FormData();
        formData.append('sender_id', selectedChat.senderId.toString());
        formData.append('platform', selectedChat.platform);
        formData.append('image_file', file);

        const response = await fetch(`${API_BASE_URL}/api/chats/reply-image`, {
          method: 'POST',
          credentials: 'include',
          body: formData,
        });

        if (!response.ok) {
          const errData = await response.json().catch(() => ({}));
          throw new Error(errData.detail || `Failed to send card for ${product.name}`);
        }

        queryClient.invalidateQueries({
          queryKey: ['chat-history', selectedChat.platform, selectedChat.senderId],
        });
        queryClient.invalidateQueries({
          queryKey: ['chats'],
        });
      }
    } catch (err) {
      console.error('Error sharing product cards:', err);
    } finally {
      setSelectedProductForCard(null);
      setIsGeneratingCard(false);
      setCardLoadingProgress('');
    }
  };

  const handleToggleAI = async () => {
    if (!chat || !selectedChat) return;
    try {
      await toggleAIMutation.mutateAsync({
        sender_id: selectedChat.senderId,
        platform: selectedChat.platform,
        ai_assigned: !chat.ai_assigned,
      });
    } catch (err) {
      console.error('Failed to toggle AI assignment:', err);
    }
  };
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
          
          {chat?.user.profile_pic ? (
            <img
              src={chat.user.profile_pic}
              alt={chat.user.sender_name || 'User'}
              className="w-10 h-10 rounded-full object-cover border border-white shadow-sm"
              onError={(e) => {
                (e.target as HTMLImageElement).style.display = 'none';
                const fallback = document.getElementById('chat-header-fallback');
                if (fallback) fallback.style.display = 'flex';
              }}
            />
          ) : null}
          <div
            id="chat-header-fallback"
            style={{ display: chat?.user.profile_pic ? 'none' : 'flex' }}
            className="w-10 h-10 rounded-full bg-indigo-100 flex items-center justify-center text-indigo-600 font-bold border border-white"
          >
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
                {selectedChat.platform === 'tiktok' && <FaTiktok className="w-3.5 h-3.5 text-black" />}
                {selectedChat.platform === 'whatsapp' && <FaWhatsapp className="w-3.5 h-3.5 text-green-500" />}
                {selectedChat.platform === 'messenger' && <FaFacebookMessenger className="w-3.5 h-3.5 text-blue-600" />}
                {selectedChat.platform} DM
              </span>
            </div>
            <p className="text-[10px] text-slate-400 font-medium">
              {chat?.user.sender_username ? `@${chat.user.sender_username}` : 'No username'}
            </p>
          </div>
        </div>
        
        <div className="flex items-center gap-3 relative">
          {chat && (
            <button
              type="button"
              onClick={handleToggleAI}
              disabled={toggleAIMutation.isPending}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-xl border text-xs font-bold transition-all duration-200 cursor-pointer disabled:opacity-50 select-none shadow-sm
                ${chat.ai_assigned
                  ? 'bg-indigo-600 border-indigo-600 text-white hover:bg-indigo-700 shadow-indigo-100'
                  : 'bg-white border-slate-200 text-slate-600 hover:bg-slate-50'}`}
            >
              <Sparkles className={`w-3.5 h-3.5 ${chat.ai_assigned ? 'text-white animate-pulse' : 'text-indigo-500'}`} />
              <span>AI Auto-Reply: {chat.ai_assigned ? 'ON' : 'OFF'}</span>
            </button>
          )}

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
              {isInbound && chat?.user.profile_pic ? (
                <img
                  src={chat.user.profile_pic}
                  alt={chat.user.sender_name || 'User'}
                  className="w-8 h-8 rounded-full object-cover border border-white shadow-sm flex-shrink-0"
                  onError={(e) => {
                    (e.target as HTMLImageElement).style.display = 'none';
                    const fallback = document.getElementById(`msg-fallback-${msg.message_id}`);
                    if (fallback) fallback.style.display = 'flex';
                  }}
                />
              ) : null}
              <div
                id={`msg-fallback-${msg.message_id}`}
                style={{ display: isInbound && chat?.user.profile_pic ? 'none' : 'flex' }}
                className={`w-8 h-8 rounded-full flex-shrink-0 flex items-center justify-center text-[10px] font-bold border border-white
                  ${isInbound ? 'bg-indigo-100 text-indigo-600' : 'bg-indigo-600 text-white shadow-lg'}`}
              >
                {isInbound ? initials : orgInitials}
              </div>
              <div className={`space-y-1 ${isInbound ? '' : 'items-end flex flex-col'}`}>
                <div className={`p-4 rounded-2xl shadow-sm text-sm leading-relaxed relative
                  ${isInbound 
                    ? 'bg-white/80 backdrop-blur-md border border-indigo-50 rounded-tl-none text-slate-700' 
                    : 'bg-indigo-50 border border-indigo-200 rounded-tr-none text-slate-800'}`}
                >
                  {msg.image_url && (
                    <div className="mb-2 max-w-[280px] rounded-lg overflow-hidden border border-slate-100 bg-white flex items-center justify-center">
                      {(() => {
                        const url = msg.image_url.toLowerCase();
                        const videoExtensions = ['.mp4', '.mov', '.webm', '.mkv', '.avi', '.3gp', '.ogg'];
                        const isVideo = videoExtensions.some(ext => url.endsWith(ext) || url.includes(ext + '?') || url.includes(ext + '#')) || url.includes('/video/upload/') || url.includes('/video/');
                        
                        if (isVideo) {
                          return (
                            <video 
                              src={msg.image_url} 
                              controls 
                              preload="metadata" 
                              className="w-full h-auto max-h-[300px] rounded"
                            />
                          );
                        }
                        return (
                          <img 
                            src={msg.image_url} 
                            alt="Attached media" 
                            className="w-full h-auto object-contain max-h-[300px]" 
                          />
                        );
                      })()}
                    </div>
                  )}
                  {msg.text && msg.text !== "Shared a product card" && <div className="whitespace-pre-wrap">{renderMessageText(msg.text)}</div>}
                  {isInbound && msg.intent === 'buy' && (
                    <div className="mt-2 flex items-center gap-1.5 select-none">
                      <span className="px-2 py-0.5 rounded-full bg-emerald-50 text-emerald-700 border border-emerald-200/50 text-[9px] font-extrabold tracking-wider uppercase flex items-center gap-1 shadow-sm">
                        <ShoppingBag className="w-2.5 h-2.5 text-emerald-600" />
                        Buy Intent
                      </span>
                    </div>
                  )}
                </div>
                <div className="flex items-center gap-2 px-1">
                  <span className="text-[10px] font-medium text-slate-400">{msgTime}</span>
                  {!isInbound && (
                    <span title={msg.seen ? 'Seen' : 'Sent'}>
                      <CheckCircle2
                        className={`w-3 h-3 ${msg.seen ? 'text-blue-500 font-bold' : 'text-slate-300'}`}
                      />
                    </span>
                  )}
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
            <button 
              type="button" 
              onClick={() => {
                setShowActions(false);
                setIsCreateTicketOpen(true);
              }} 
              className="flex items-center gap-3 px-4 py-2 hover:bg-indigo-50/50 rounded-xl text-slate-600 text-xs font-semibold cursor-pointer"
            >
              <Ticket className="w-4 h-4 text-indigo-500" />
              <span>Create Ticket</span>
            </button>
            <button 
              type="button" 
              onClick={() => {
                setShowActions(false);
                fileInputRef.current?.click();
              }} 
              className="flex items-center gap-3 px-4 py-2 hover:bg-indigo-50/50 rounded-xl text-slate-600 text-xs font-semibold cursor-pointer"
            >
              <ImageIcon className="w-4 h-4 text-pink-500" />
              <span>Upload Image</span>
            </button>
            <button 
              type="button" 
              onClick={() => {
                setShowActions(false);
                setIsProductSelectorOpen(true);
              }} 
              className="flex items-center gap-3 px-4 py-2 hover:bg-indigo-50/50 rounded-xl text-slate-600 text-xs font-semibold cursor-pointer"
            >
              <Package className="w-4 h-4 text-amber-500" />
              <span>Add Product</span>
            </button>
            <button 
              type="button" 
              onClick={() => {
                setShowActions(false);
                setIsCreateOrderOpen(true);
              }} 
              className="flex items-center gap-3 px-4 py-2 hover:bg-indigo-50/50 rounded-xl text-slate-600 text-xs font-semibold cursor-pointer"
            >
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

      {/* Product Selector Dialog Modal */}
      <ProductShareModal 
        key={isProductSelectorOpen ? 'product-selector-open' : 'product-selector-closed'}
        open={isProductSelectorOpen} 
        onOpenChange={setIsProductSelectorOpen} 
        onSelect={handleSelectProduct} 
      />

      {/* Create Order Dialog Modal */}
      <CreateOrderModal 
        key={isCreateOrderOpen ? 'create-order-open' : 'create-order-closed'}
        open={isCreateOrderOpen} 
        onOpenChange={setIsCreateOrderOpen} 
        selectedChat={selectedChat} 
        customerName={chat?.user?.sender_name}
      />

      {/* Create Ticket Dialog Modal */}
      <CreateTicketModal 
        key={isCreateTicketOpen ? 'create-ticket-open' : 'create-ticket-closed'}
        open={isCreateTicketOpen} 
        onOpenChange={setIsCreateTicketOpen} 
        selectedChat={selectedChat}
        customerName={data?.chat?.user?.sender_name}
      />

      {/* Hidden Card Template for SVG-to-PNG conversion */}
      {selectedProductForCard && (
        <div style={{ position: 'absolute', left: '-9999px', top: '-9999px', pointerEvents: 'none' }}>
          <div 
            ref={cardRef} 
            style={{ width: '800px', height: '1100px' }}
            className="relative rounded-3xl overflow-hidden bg-white border border-slate-100 flex flex-col font-sans"
          >
            {/* Top Product Image (Large Window) */}
            <div className="w-full h-[750px] bg-slate-50 relative overflow-hidden flex items-center justify-center border-b border-slate-100">
              {selectedProductForCard.image ? (
                <img 
                  src={selectedProductForCard.image} 
                  alt={selectedProductForCard.name} 
                  className="w-full h-full object-cover"
                  crossOrigin="anonymous"
                />
              ) : (
                <Package className="w-32 h-32 text-slate-300" />
              )}
            </div>

            {/* Bottom Info Section (Clean White Area) */}
            <div className="w-full h-[350px] p-10 bg-white flex flex-col justify-between">
              <div>
                <h3 className="text-3xl font-extrabold text-slate-900 leading-tight line-clamp-1">
                  {selectedProductForCard.name}
                </h3>
                <p className="text-base text-slate-500 mt-4 line-clamp-3 leading-relaxed">
                  {selectedProductForCard.description || 'No description provided.'}
                </p>
              </div>
              
              <div className="flex items-center justify-between mt-auto">
                <span className="text-4xl font-black text-indigo-600">
                  {new Intl.NumberFormat('en-US', {
                    style: 'currency',
                    currency: selectedProductForCard.currency,
                  }).format(selectedProductForCard.price / 100)}
                </span>
                <span className="px-4 py-2 bg-indigo-50 text-indigo-600 rounded-xl text-sm font-bold border border-indigo-100">
                  Quick Details
                </span>
              </div>
            </div>
          </div>
        </div>
      )}
      {/* Loading Overlay for card generation */}
      {isGeneratingCard && (
        <div className="absolute inset-0 bg-slate-900/40 backdrop-blur-sm flex items-center justify-center z-50 transition-all duration-300 animate-in fade-in">
          <div className="bg-white p-6 rounded-2xl border border-slate-100 shadow-2xl flex flex-col items-center gap-4 max-w-[280px] w-full mx-4">
            <div className="relative w-12 h-12 flex items-center justify-center">
              <div className="w-12 h-12 border-4 border-indigo-200 rounded-full absolute" />
              <div className="w-12 h-12 border-4 border-indigo-600 border-t-transparent rounded-full animate-spin absolute" />
            </div>
            <div className="text-center space-y-1">
              <h4 className="text-xs font-bold text-slate-800">Sharing Product Cards</h4>
              <p className="text-[10px] text-slate-500 font-semibold animate-pulse">{cardLoadingProgress || 'Processing...'}</p>
            </div>
          </div>
        </div>
      )}
      <input 
        type="file" 
        ref={fileInputRef} 
        onChange={handleImageUpload} 
        multiple 
        accept="image/*" 
        style={{ display: 'none' }} 
      />
    </div>
  );
};
