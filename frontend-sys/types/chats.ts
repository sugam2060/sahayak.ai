import { Product } from './product';

export interface MessageDetail {
  message_id: number;
  direction: 'inbound' | 'outbound';
  sender_id: string | number;
  sender_name: string;
  text: string;
  image_url?: string;
  intent?: 'buy' | 'no_intent';
  seen?: boolean;
  created_at: string;
  message_type?: string;
  product_data?: Product;
}

export interface ConversationUser {
  sender_id: string | number;
  sender_name: string;
  sender_username: string | null;
  profile_pic?: string | null;
}

export interface Conversation {
  _id: string;
  organization_id: string;
  platform: string;
  bot_id: string | null;
  locker_name?: string | null;
  chat_id: string | number;
  user: ConversationUser;
  messages: MessageDetail[];
  ai_assigned: boolean;
  handoff_pending?: boolean;
  created_at: string;
  updated_at: string;
  ai_event?: { event: string; status: string };
}

export interface SendReplyRequest {
  sender_id: string | number;
  platform: string;
  text: string;
}
