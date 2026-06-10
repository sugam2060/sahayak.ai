export interface CustomerChatRequest {
  platform: string;
  sender_id: string;
  status: 'pending' | 'accepted' | 'declined';
}

export interface HandoffRequest {
  id: string;
  conversation_id: string;
  requester_id: string;
  handler_id: string;
  org_id: string;
  status: 'pending' | 'granted' | 'declined' | 'expired';
  timestamp: number;
}

export interface InternalMessage {
  message_id: string;
  sender_id: string;
  sender_name: string;
  text: string;
  message_type: 'text' | 'customer_chat_request' | 'handoff_request';
  customer_chat_request?: CustomerChatRequest;
  handoff_request?: HandoffRequest;
  created_at: string;
}

export interface InternalConversation {
  _id: string;
  organization_id: string;
  type: 'direct' | 'group' | 'org';
  user_ids: string[];
  group_name: string | null;
  group_admin_ids: string[];
  messages: InternalMessage[];
  created_at: string;
  updated_at: string;
}

export interface InternalMember {
  user_id: string;
  full_name: string;
  role: string;
  email: string;
}
