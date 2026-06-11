'use client';

import React, { useEffect, useState, useRef } from 'react';
import { createPortal } from 'react-dom';
import { MessageSquareCode } from 'lucide-react';
import { useAuthStore } from '@/store/authStore';
import { useQueryClient } from '@tanstack/react-query';
import { InternalChatDialog } from './InternalChatDialog';
import { toast } from 'sonner';
import { useUnreadStore } from '@/store/unreadStore';

export const InternalChatFAB: React.FC = () => {
  const [open, setOpen] = useState(false);
  const [mounted, setMounted] = useState(false);
  
  const user = useAuthStore((state) => state.user);
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);
  
  const incrementUnread = useUnreadStore((state) => state.increment);
  const totalUnread = useUnreadStore((state) => state.getTotalUnread());
  const setIsDialogOpen = useUnreadStore((state) => state.setIsDialogOpen);

  useEffect(() => {
    setIsDialogOpen(open);
  }, [open, setIsDialogOpen]);
  
  const socketRef = useRef<WebSocket | null>(null);
  const queryClient = useQueryClient();

  useEffect(() => {
    const timer = setTimeout(() => setMounted(true), 0);
    return () => {
      clearTimeout(timer);
      setMounted(false);
    };
  }, []);

  // Set up WebSocket connection when user is authenticated
  useEffect(() => {
    if (!isAuthenticated || !user?.organization_id || !user?.user_id) {
      if (socketRef.current) {
        socketRef.current.close();
        socketRef.current = null;
      }
      return;
    }

    const apiBaseUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
    const wsProto = apiBaseUrl.startsWith('https:') ? 'wss:' : 'ws:';
    const wsHost = apiBaseUrl.replace(/^https?:\/\//, '').replace(/\/$/, '');
    
    const wsUrl = `${wsProto}//${wsHost}/api/internal-chats/ws/${user.organization_id}?user_id=${user.user_id}`;
    
    console.log(`[Internal WebSocket] Connecting to: ${wsUrl}`);
    const socket = new WebSocket(wsUrl);
    socketRef.current = socket;

    socket.onopen = () => {
      console.log('[Internal WebSocket] Connection established.');
    };

    socket.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        const { type, event_type, convo_id, user_ids } = data;

        if (event_type === 'new_message') {
          // Play a micro-notification noise or show message toast if the chat is closed
          const isMsgFromMe = String(data.message.sender_id) === String(user.user_id);
          if (!isMsgFromMe && !open) {
            toast(`New message from ${data.message.sender_name}`, {
              description: data.message.text,
              action: {
                label: 'Reply',
                onClick: () => setOpen(true),
              },
            });
          }

          // Increment unread store!
          if (!isMsgFromMe) {
            let key = '';
            if (type === 'direct') {
              key = String(data.message.sender_id);
            } else if (type === 'group') {
              key = convo_id;
            } else if (type === 'org') {
              key = 'org';
            }
            if (key) {
              incrementUnread(key);
            }
          }

          // Invalidate tanstack caches for real-time update
          if (type === 'direct') {
            const targetUserId = user_ids.find((id: string) => String(id) !== String(user.user_id));
            queryClient.invalidateQueries({ queryKey: ['internal-direct-history', targetUserId] });
          } else if (type === 'group') {
            queryClient.invalidateQueries({ queryKey: ['internal-group-history', convo_id] });
          } else if (type === 'org') {
            queryClient.invalidateQueries({ queryKey: ['internal-org-history'] });
          }
        } 
        
        else if (event_type === 'group_created') {
          queryClient.invalidateQueries({ queryKey: ['internal-groups'] });
          if (!open && user_ids.includes(user.user_id)) {
            toast.info(`You were added to a new group: ${data.conversation.group_name}`);
          }
        } 
        
        else if (event_type === 'group_deleted') {
          queryClient.invalidateQueries({ queryKey: ['internal-groups'] });
          queryClient.invalidateQueries({ queryKey: ['internal-group-history', convo_id] });
          if (!open && user_ids.includes(user.user_id)) {
            toast.info(`Group "${data.conversation.group_name}" has been deleted.`);
          }
        }

        else if (event_type === 'group_members_updated') {
          queryClient.invalidateQueries({ queryKey: ['internal-group-history', convo_id] });
          queryClient.invalidateQueries({ queryKey: ['internal-groups'] });
        } 
        
        else if (event_type === 'request_status_updated') {
          const targetUserId = user_ids.find((id: string) => String(id) !== String(user.user_id));
          queryClient.invalidateQueries({ queryKey: ['internal-direct-history', targetUserId] });
          
          // Invalidate customer locks and active chats in main inbox
          queryClient.invalidateQueries({ queryKey: ['chats'] });
          queryClient.invalidateQueries({ queryKey: ['chat-history'] });
          
          if (data.status === 'accepted') {
            toast.success('Customer chat access request was accepted.');
          } else if (data.status === 'declined') {
            toast.error('Customer chat access request was declined.');
          }
        } 
        
        else if (event_type === 'handoff_status_updated') {
          const targetUserId = user_ids.find((id: string) => String(id) !== String(user.user_id));
          queryClient.invalidateQueries({ queryKey: ['internal-direct-history', targetUserId] });
          
          // Invalidate customer locks and active chats in main inbox
          queryClient.invalidateQueries({ queryKey: ['chats'] });
          queryClient.invalidateQueries({ queryKey: ['chat-history'] });
          
          if (data.status === 'granted') {
            toast.success('Handoff request was accepted.');
          } else if (data.status === 'declined') {
            toast.error('Handoff request was declined.');
          } else if (data.status === 'expired') {
            toast.info('Handoff request expired.');
          }
        } 
        
        else if (data.type === 'error') {
          toast.error(data.message || 'An error occurred.');
        }
      } catch (err) {
        console.error('[Internal WebSocket] Message handling error:', err);
      }
    };

    socket.onclose = () => {
      console.log('[Internal WebSocket] Connection closed.');
    };

    return () => {
      socket.close();
      socketRef.current = null;
    };
  }, [isAuthenticated, user?.organization_id, user?.user_id, queryClient, open, incrementUnread]);

  const handleSendWSMessage = (
    convoId: string,
    text: string,
    chatType: 'direct' | 'group' | 'org',
    msgType: 'text' | 'customer_chat_request' = 'text',
    customerReqData?: unknown
  ) => {
    if (socketRef.current && socketRef.current.readyState === WebSocket.OPEN) {
      const payload: Record<string, unknown> = {
        type: chatType,
        text,
        message_type: msgType,
      };

      if (chatType === 'direct') {
        payload.recipient_id = convoId;
      } else if (chatType === 'group') {
        payload.group_id = convoId;
      }

      if (msgType === 'customer_chat_request' && customerReqData) {
        payload.customer_chat_request = customerReqData;
      }

      socketRef.current.send(JSON.stringify(payload));
    } else {
      toast.error('Unable to send message: WebSocket connection is disconnected.');
    }
  };

  // Auth guard and Client-side hydration safety checks
  if (!mounted || !isAuthenticated || !user) return null;

  return createPortal(
    <>
      {/* Fixed Circular FAB */}
      <button
        onClick={() => setOpen(true)}
        className="fixed left-6 bottom-8 z-50 w-12 h-12 rounded-full shadow-lg flex items-center justify-center text-white bg-gradient-to-br from-[#7C63D4] to-[#5E9EEB] hover:scale-105 active:scale-95 transition-all cursor-pointer border border-white/20 hover:shadow-xl hover:shadow-[#7C63D4]/20 animate-in fade-in zoom-in duration-300"
        title="Workspace Chat"
      >
        <MessageSquareCode size={20} className="animate-pulse" />
        {totalUnread > 0 && (
          <span className="absolute -top-1.5 -right-1.5 min-w-5 h-5 px-1.5 bg-rose-500 text-white text-[10px] font-bold rounded-full flex items-center justify-center border-2 border-white dark:border-zinc-950 animate-bounce">
            {totalUnread}
          </span>
        )}
      </button>

      {/* Internal Workspace Dialog */}
      <InternalChatDialog
        open={open}
        onOpenChange={setOpen}
        currentUserId={user.user_id || ''}
        currentUserRole={user.role || ''}
        onSendWSMessage={handleSendWSMessage}
      />
    </>,
    document.body
  );
};
