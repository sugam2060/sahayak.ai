'use client';

import React, { useState, useEffect } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { useAuthStore } from '@/store/authStore';
import { InboxSidebar } from './InboxSidebar';
import { ChatWindow } from './ChatWindow';

const InboxLayout = () => {
  const queryClient = useQueryClient();
  const { user } = useAuthStore();
  const [selectedChat, setSelectedChat] = useState<{ platform: string; senderId: number } | null>(null);
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);

  const handleSelectChat = (chat: { platform: string; senderId: number } | null) => {
    setSelectedChat(chat);
    setIsSidebarOpen(false); // Auto-close sidebar drawer on mobile after selection
  };

  useEffect(() => {
    if (!user?.organization_id) return;

    // Use absolute WebSocket URL pointing to API Gateway port 8000
    const wsProto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${wsProto}//localhost:8000/api/chats/ws/${user.organization_id}`;
    
    console.log(`[WebSocket] Connecting to: ${wsUrl}`);
    const socket = new WebSocket(wsUrl);

    socket.onopen = () => {
      console.log('[WebSocket] Connected to real-time events.');
    };

    socket.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        console.log('[WebSocket] Message event:', data);

        if (data.type === 'new_message') {
          const { platform, sender_id, message } = data;

          // 1. Update the chat history cache for this conversation
          queryClient.setQueryData(['chat-history', platform, sender_id], (oldData: any) => {
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
              (c: any) => c.platform === platform && c.user.sender_id === sender_id
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
        }
      } catch (err) {
        console.error('[WebSocket] Error parsing event message:', err);
      }
    };

    socket.onerror = (err) => {
      console.error('[WebSocket] Connection error:', err);
    };

    socket.onclose = () => {
      console.log('[WebSocket] Connection closed.');
    };

    return () => {
      socket.close();
    };
  }, [user?.organization_id, queryClient]);

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
