from datetime import datetime, timezone
from enum import Enum
from typing import Optional, List, Dict, Any, Union
from pydantic import BaseModel, Field

class MessageIntent(str, Enum):
    BUY = "buy"
    NO_INTENT = "no_intent"

class MessageDetail(BaseModel):
    message_id: int = Field(..., description="Autoincremental message ID within the conversation")
    direction: str = Field(..., description="inbound or outbound")
    sender_id: Union[int, str] = Field(..., description="Telegram/Instagram user ID or bot account ID")
    sender_name: str = Field(..., description="User's full name or bot name")
    text: str = Field(..., description="Message text content")
    image_url: Optional[str] = Field(default=None, description="URL of an image attached to this message")
    intent: Optional[MessageIntent] = Field(default=MessageIntent.NO_INTENT, description="Intent of the message")
    assigned_user: Optional[str] = Field(default=None, description="UUID of the user/agent who sent this outbound message")
    seen: bool = Field(default=False, description="Whether the message has been seen/read")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class ConversationUser(BaseModel):
    sender_id: Union[int, str] = Field(..., description="Unique ID of the sender on this platform")
    sender_name: str = Field(..., description="Display name of the sender")
    sender_username: Optional[str] = Field(None, description="Username of the sender")
    profile_pic: Optional[str] = Field(None, description="Profile picture URL of the sender")

class ConversationMongo(BaseModel):
    organization_id: str = Field(..., description="References PostgreSQL Organization ID")
    platform: str = Field(..., description="e.g. telegram")
    bot_id: Optional[str] = Field(default=None, description="ID of the user or AI bot currently locking this conversation")
    chat_id: Union[int, str] = Field(..., description="Telegram chat ID or other platform equivalent")
    user: ConversationUser = Field(..., description="The user participating in the conversation")
    messages: List[MessageDetail] = Field(default_factory=list, description="Array of messages in this conversation")
    ai_assigned: bool = Field(default=False, description="Whether this conversation is handled automatically by AI")
    assigned_user: Optional[str] = Field(None, description="UUID of the user/agent assigned to this conversation")
    allowed_users: List[str] = Field(default_factory=list, description="List of user UUIDs allowed to access this conversation when locked")
    previous_summary: Optional[str] = Field(None, description="Summarized history of past messages")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = {
        "populate_by_name": True
    }

