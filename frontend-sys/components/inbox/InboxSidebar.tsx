'use client';

import React, { useState } from 'react';
import { Search, Filter, MessageCircle } from 'lucide-react';
import { FaInstagram, FaTwitter, FaTelegram } from 'react-icons/fa';
import { useChats } from '@/services/api/chats';
import { useAuthStore } from '@/store/authStore';

interface InboxSidebarProps {
  selectedChat: { platform: string; senderId: number } | null;
  setSelectedChat: (chat: { platform: string; senderId: number } | null) => void;
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
    const date = parseDate(isoString);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));
    
    if (diffDays === 0) {
      return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    } else if (diffDays === 1) {
      return 'Yesterday';
    } else if (diffDays < 7) {
      return date.toLocaleDateString([], { weekday: 'short' });
    } else {
      return date.toLocaleDateString([], { month: 'short', day: 'numeric' });
    }
  } catch (e) {
    return '';
  }
};

export const InboxSidebar = ({ selectedChat, setSelectedChat }: InboxSidebarProps) => {
  const { user } = useAuthStore();
  const { data, isLoading, error } = useChats(user?.organization_id);
  const [searchQuery, setSearchQuery] = useState('');
  const [activeFilter, setActiveFilter] = useState('All');

  const chats = data?.chats || [];

  const filteredChats = chats.filter((convo) => {
    const lastMsg = convo.messages[convo.messages.length - 1];
    const lastText = lastMsg ? lastMsg.text.toLowerCase() : '';
    const name = convo.user.sender_name.toLowerCase();
    const username = convo.user.sender_username?.toLowerCase() || '';
    const matchesSearch = name.includes(searchQuery.toLowerCase()) || 
                          username.includes(searchQuery.toLowerCase()) || 
                          lastText.includes(searchQuery.toLowerCase());
                          
    if (!matchesSearch) return false;
    
    if (activeFilter === 'All') return true;
    if (activeFilter === 'Unread') {
      return lastMsg && lastMsg.direction === 'inbound';
    }
    if (activeFilter === 'Mine') {
      return convo.messages.some(m => m.direction === 'outbound');
    }
    if (activeFilter === 'Telegram') {
      return convo.platform === 'telegram';
    }
    return true;
  });

  return (
    <div className="w-full h-full flex flex-col border-r border-indigo-100/50 bg-white/70 backdrop-blur-xl">
      <div className="p-4 space-y-4">
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
          <input 
            type="text" 
            placeholder="Search conversations..." 
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-10 pr-4 py-2 bg-slate-100/50 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500/20"
          />
        </div>
        
        <div className="flex items-center gap-2 overflow-x-auto no-scrollbar pb-2">
          {['All', 'Unread', 'Mine', 'Telegram'].map((filter) => (
            <button 
              key={filter}
              onClick={() => setActiveFilter(filter)}
              className={`px-3 py-1.5 rounded-full text-xs font-medium whitespace-nowrap transition-colors cursor-pointer
                ${activeFilter === filter ? 'bg-indigo-50 text-indigo-600 border border-indigo-200' : 'bg-white/50 text-slate-600 border border-slate-200 hover:bg-slate-50'}`}
            >
              {filter}
            </button>
          ))}
          <button className="p-1.5 rounded-full bg-white/50 border border-slate-200 text-slate-500 cursor-pointer">
            <Filter className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto">
        <div className="px-4 py-2">
          <span className="text-[10px] font-bold text-slate-400 tracking-wider uppercase">Active Conversations</span>
        </div>
        
        {isLoading && (
          <div className="p-8 text-center text-slate-500 flex flex-col items-center gap-2">
            <div className="w-6 h-6 border-2 border-indigo-600 border-t-transparent rounded-full animate-spin" />
            <span className="text-xs">Loading conversations...</span>
          </div>
        )}

        {error && (
          <div className="p-4 text-center text-xs text-rose-500">
            Failed to load chats: {(error as any).message}
          </div>
        )}

        {!isLoading && !error && filteredChats.length === 0 && (
          <div className="p-8 text-center text-xs text-slate-400">
            No conversations found.
          </div>
        )}

        {!isLoading && !error && filteredChats.map((convo) => {
          const lastMsg = convo.messages[convo.messages.length - 1];
          const lastText = lastMsg 
            ? (lastMsg.image_url || lastMsg.text === 'Shared a product card' ? '📷 Image shared' : lastMsg.text)
            : 'No messages yet';
          const lastTime = convo.updated_at ? formatTime(convo.updated_at) : '';
          const initials = convo.user.sender_name
            .split(' ')
            .map((n) => n[0])
            .join('')
            .toUpperCase()
            .slice(0, 2);

          const isSelected = selectedChat?.platform === convo.platform && 
                             selectedChat?.senderId === convo.user.sender_id;

          return (
            <div 
              key={convo._id}
              onClick={() => setSelectedChat({ platform: convo.platform, senderId: convo.user.sender_id })}
              className={`px-4 py-3 flex gap-3 cursor-pointer transition-all border-l-4 
                ${isSelected ? 'bg-indigo-50/50 border-indigo-600' : 'border-transparent hover:bg-slate-50/50'}`}
            >
              <div className="relative flex-shrink-0">
                <div className="w-12 h-12 rounded-full bg-indigo-100 flex items-center justify-center text-indigo-600 font-bold border-2 border-white shadow-sm">
                  {initials || '??'}
                </div>
                <div className="absolute -right-0.5 -bottom-0.5 w-5 h-5 rounded-full bg-white p-1 shadow-sm border border-slate-100 flex items-center justify-center">
                  {convo.platform === 'instagram' && <FaInstagram className="w-full h-full text-pink-600" />}
                  {convo.platform === 'telegram' && <FaTelegram className="w-full h-full text-blue-500" />}
                  {convo.platform === 'twitter' && <FaTwitter className="w-full h-full text-blue-400" />}
                  {convo.platform !== 'instagram' && convo.platform !== 'telegram' && convo.platform !== 'twitter' && (
                    <MessageCircle className="w-full h-full text-indigo-500" />
                  )}
                </div>
                <div className="absolute -left-0.5 -top-0.5 w-3 h-3 rounded-full border-2 border-white bg-teal-500" />
              </div>
              
              <div className="flex-1 min-w-0">
                <div className="flex items-center justify-between mb-1">
                  <h4 className="text-sm font-semibold text-slate-900 truncate">{convo.user.sender_name}</h4>
                  <span className="text-[10px] font-medium text-slate-400">{lastTime}</span>
                </div>
                <p className="text-xs text-slate-500 line-clamp-1 mb-2">
                  {lastText}
                </p>
                <div className="flex items-center justify-between">
                  <div className="flex gap-1.5">
                    <span className="px-1.5 py-0.5 bg-indigo-50 text-[9px] font-bold text-indigo-600 rounded-sm uppercase tracking-tight">
                      {convo.platform}
                    </span>
                  </div>
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};
