from datetime import datetime, timezone
from enum import Enum
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field

class MessageIntent(str, Enum):
    BUY = "buy"
    NO_INTENT = "no_intent"

class MessageDetail(BaseModel):
    message_id: int = Field(..., description="Autoincremental message ID within the conversation")
    direction: str = Field(..., description="inbound or outbound")
    sender_id: int = Field(..., description="Telegram user ID or bot account ID")
    sender_name: str = Field(..., description="User's full name or bot name")
    text: str = Field(..., description="Message text content")
    intent: Optional[MessageIntent] = Field(default=MessageIntent.NO_INTENT, description="Intent of the message")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class ConversationUser(BaseModel):
    sender_id: int = Field(..., description="Unique ID of the sender on this platform")
    sender_name: str = Field(..., description="Display name of the sender")
    sender_username: Optional[str] = Field(None, description="Username of the sender")

class ConversationMongo(BaseModel):
    organization_id: str = Field(..., description="References PostgreSQL Organization ID")
    platform: str = Field(..., description="e.g. telegram")
    bot_name: str = Field(..., description="Name of the bot handling this conversation")
    chat_id: int = Field(..., description="Telegram chat ID")
    user: ConversationUser = Field(..., description="The user participating in the conversation")
    messages: List[MessageDetail] = Field(default_factory=list, description="Array of messages in this conversation")
    ai_assigned: bool = Field(default=False, description="Whether this conversation is handled automatically by AI")
    previous_summary: Optional[str] = Field(None, description="Summarized history of past messages")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = {
        "populate_by_name": True
    }
