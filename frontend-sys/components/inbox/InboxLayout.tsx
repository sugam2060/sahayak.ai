/* eslint-disable @typescript-eslint/no-explicit-any */
'use client';

import React, { useState, useEffect, useMemo } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { useAuthStore } from '@/store/authStore';
import { InboxSidebar } from './InboxSidebar';
import { ChatWindow } from './ChatWindow';
import { useChats } from '@/services/api/chats';

const parseDate = (dateStr: string) => {
  if (!dateStr) return new Date();
  const timePart = dateStr.split('T')[1];
  const hasTimezone = dateStr.endsWith('Z') || 
                      (timePart && (timePart.includes('+') || timePart.includes('-')));
  return new Date(hasTimezone ? dateStr : `${dateStr}Z`);
};

const InboxLayout = () => {
  const queryClient = useQueryClient();
  const { user } = useAuthStore();
  const [selectedChat, setSelectedChat] = useState<{ platform: string; senderId: string } | null>(null);
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);

  // Fetch chats to verify active chats and select latest
  const { data } = useChats(user?.organization_id);
  const chats = useMemo(() => data?.chats || [], [data]);

  const handleSelectChat = (chat: { platform: string; senderId: string } | null) => {
    setSelectedChat(chat);
    setIsSidebarOpen(false); // Auto-close sidebar drawer on mobile after selection
  };

  // Automatically select the latest chat if there are chats and none is selected
  useEffect(() => {
    if (chats.length > 0 && !selectedChat) {
      const latestChat = chats[0];
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setSelectedChat({
        platform: latestChat.platform,
        senderId: String(latestChat.user.sender_id),
      });
    }
  }, [chats, selectedChat]);

  useEffect(() => {
    // Only connect if user is authenticated, has an organization_id, and there is at least one active chat
    if (!user?.organization_id || chats.length === 0) return;

    // Use absolute WebSocket URL derived from NEXT_PUBLIC_API_URL
    const apiBaseUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
    const wsProto = apiBaseUrl.startsWith('https:') ? 'wss:' : 'ws:';
    const wsHost = apiBaseUrl.replace(/^https?:\/\//, '').replace(/\/$/, '');

    // Pass user_id, platform, and sender_id to restrict connections per chat
    const queryParams = new URLSearchParams();
    if (user?.user_id) queryParams.append('user_id', user.user_id);
    if (selectedChat) {
      queryParams.append('platform', selectedChat.platform);
      queryParams.append('sender_id', selectedChat.senderId);
    }

    const wsUrl = `${wsProto}//${wsHost}/api/chats/ws/${user.organization_id}?${queryParams.toString()}`;
    
    console.log(`[WebSocket] Connecting to: ${wsUrl}`);
    let isClosed = false;
    const socket = new WebSocket(wsUrl);

    socket.onopen = () => {
      if (isClosed) return;
      console.log('[WebSocket] Connected to real-time events.');
    };

    socket.onmessage = (event) => {
      if (isClosed) return;
      try {
        const data = JSON.parse(event.data);
        console.log('[WebSocket] Message event:', data);

        if (data.type === 'new_message') {
          const { platform, sender_id, message } = data;
          const sender_id_str = String(sender_id);

          // 1. Update the chat history cache for this conversation
          queryClient.setQueryData(['chat-history', platform, sender_id_str], (oldData: any) => {
            if (!oldData || !oldData.chat) return oldData;
            const currentMsgs = oldData.chat.messages || [];
            // Check for duplicates
            if (currentMsgs.some((m: any) => m.message_id === message.message_id)) {
              return oldData;
            }
            return {
              ...oldData,
              chat: {
                ...oldData.chat,
                messages: [...currentMsgs, message],
                updated_at: new Date().toISOString()
              }
            };
          });

          // 2. Update the main chats list cache
          queryClient.setQueryData(['chats', user.organization_id], (oldData: any) => {
            if (!oldData || !oldData.chats) return oldData;
            const chatsList = [...oldData.chats];
            const idx = chatsList.findIndex(
              (c: any) => c.platform === platform && String(c.user.sender_id) === sender_id_str
            );

            if (idx !== -1) {
              const updatedChat = {
                ...chatsList[idx],
                updated_at: new Date().toISOString(),
                messages: [...(chatsList[idx].messages || []), message]
              };
              // Splice out and put at the top of the list
              chatsList.splice(idx, 1);
              chatsList.unshift(updatedChat);
            } else {
              // Invalidate to refetch the full list if this is a brand new chat
              queryClient.invalidateQueries({ queryKey: ['chats', user.organization_id] });
            }

            return {
              ...oldData,
              chats: chatsList
            };
          });
        } else if (data.type === 'ai_assigned_toggle') {
          const { platform, sender_id, ai_assigned } = data;
          const sender_id_str = String(sender_id);

          // 1. Update the chat history cache for this conversation
          queryClient.setQueryData(['chat-history', platform, sender_id_str], (oldData: any) => {
            if (!oldData || !oldData.chat) return oldData;
            return {
              ...oldData,
              chat: {
                ...oldData.chat,
                ai_assigned: ai_assigned
              }
            };
          });

          // 2. Update the main chats list cache
          queryClient.setQueryData(['chats', user.organization_id], (oldData: any) => {
            if (!oldData || !oldData.chats) return oldData;
            const chatsList = [...oldData.chats];
            const idx = chatsList.findIndex(
              (c: any) => c.platform === platform && String(c.user.sender_id) === sender_id_str
            );
            if (idx !== -1) {
              chatsList[idx] = {
                ...chatsList[idx],
                ai_assigned: ai_assigned
              };
            }
            return {
              ...oldData,
              chats: chatsList
            };
          });
        } else if (data.type === 'chat_read_update') {
          const { platform, sender_id } = data;
          const sender_id_str = String(sender_id);

          // 1. Update the chat history cache
          queryClient.setQueryData(['chat-history', platform, sender_id_str], (oldData: any) => {
            if (!oldData || !oldData.chat) return oldData;
            const updatedMsgs = (oldData.chat.messages || []).map((m: any) => {
              if (m.direction === 'inbound') {
                return { ...m, seen: true };
              }
              return m;
            });
            return {
              ...oldData,
              chat: { ...oldData.chat, messages: updatedMsgs }
            };
          });

          // 2. Update the main chats list cache
          queryClient.setQueryData(['chats', user.organization_id], (oldData: any) => {
            if (!oldData || !oldData.chats) return oldData;
            const chatsList = (oldData.chats || []).map((c: any) => {
              if (c.platform === platform && String(c.user.sender_id) === sender_id_str) {
                const updatedMsgs = (c.messages || []).map((m: any) => {
                  if (m.direction === 'inbound') {
                    return { ...m, seen: true };
                  }
                  return m;
                });
                return { ...c, messages: updatedMsgs };
              }
              return c;
            });
            return { ...oldData, chats: chatsList };
          });
        } else if (data.type === 'chat_seen_update') {
          const { platform, sender_id, watermark } = data;
          const sender_id_str = String(sender_id);
          const watermarkTime = Number(watermark);

          // 1. Update the chat history cache
          queryClient.setQueryData(['chat-history', platform, sender_id_str], (oldData: any) => {
            if (!oldData || !oldData.chat) return oldData;
            const updatedMsgs = (oldData.chat.messages || []).map((m: any) => {
              if (m.direction === 'outbound' && !m.seen) {
                const msgTime = parseDate(m.created_at).getTime();
                if (msgTime <= watermarkTime) {
                  return { ...m, seen: true };
                }
              }
              return m;
            });
            return {
              ...oldData,
              chat: { ...oldData.chat, messages: updatedMsgs }
            };
          });

          // 2. Update the main chats list cache
          queryClient.setQueryData(['chats', user.organization_id], (oldData: any) => {
            if (!oldData || !oldData.chats) return oldData;
            const chatsList = (oldData.chats || []).map((c: any) => {
              if (c.platform === platform && String(c.user.sender_id) === sender_id_str) {
                const updatedMsgs = (c.messages || []).map((m: any) => {
                  if (m.direction === 'outbound' && !m.seen) {
                    const msgTime = parseDate(m.created_at).getTime();
                    if (msgTime <= watermarkTime) {
                      return { ...m, seen: true };
                    }
                  }
                  return m;
                });
                return { ...c, messages: updatedMsgs };
              }
              return c;
            });
            return { ...oldData, chats: chatsList };
          });
        }
      } catch (err) {
        console.error('[WebSocket] Error parsing event message:', err);
      }
    };

    socket.onerror = () => {
      if (isClosed) return;
      console.error('[WebSocket] Connection failed. Check if API gateway is online.');
    };

    socket.onclose = () => {
      if (isClosed) return;
      console.log('[WebSocket] Connection closed.');
    };

    return () => {
      isClosed = true;
      socket.close();
    };
  }, [user?.organization_id, user?.user_id, chats.length, queryClient, selectedChat]);

  return (
    <div className="flex h-[calc(100vh-80px)] md:h-[calc(100vh-130px)] w-full overflow-hidden bg-[#EBF1FB] rounded-2xl border border-indigo-100/30 shadow-md relative">
      {/* Mobile Sidebar Backdrop Overlay */}
      {isSidebarOpen && (
        <div 
          className="fixed inset-0 bg-slate-900/40 backdrop-blur-sm z-40 md:hidden transition-opacity duration-300"
          onClick={() => setIsSidebarOpen(false)}
        />
      )}

      {/* Zone B: Sidebar (Drawer on mobile, inline on desktop) */}
      <div 
        className={`fixed inset-y-0 left-0 z-50 w-[290px] h-full transform transition-transform duration-300 ease-in-out md:relative md:transform-none md:z-0 md:flex-shrink-0
          ${isSidebarOpen ? 'translate-x-0' : '-translate-x-full md:translate-x-0'}`}
      >
        <InboxSidebar selectedChat={selectedChat} setSelectedChat={handleSelectChat} />
      </div>
      
      {/* Zone C: Main Chat Area */}
      <div className="flex-1 h-full flex flex-col min-w-0">
        <ChatWindow 
          selectedChat={selectedChat} 
          onMenuClick={() => setIsSidebarOpen(true)}
        />
      </div>
    </div>
  );
};

export default InboxLayout;
