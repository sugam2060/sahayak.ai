from datetime import datetime, timezone
from typing import Optional, List
from pydantic import BaseModel, Field
from uuid import uuid4

class CustomerChatRequestDetail(BaseModel):
    platform: str = Field(..., description="Customer chat platform, e.g. telegram")
    sender_id: str = Field(..., description="Customer sender ID")
    status: str = Field(default="pending", description="pending, accepted, or declined")

class HandoffRequestDetail(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()), description="Unique handoff request ID")
    conversation_id: str = Field(..., description="The customer conversation being handed off")
    requester_id: str = Field(..., description="User ID requesting the handoff")
    handler_id: str = Field(..., description="User ID currently handling the chat")
    org_id: str = Field(..., description="Organization ID")
    status: str = Field(default="pending", description="pending, granted, declined, or expired")
    timestamp: int = Field(default_factory=lambda: int(datetime.now(timezone.utc).timestamp() * 1000), description="Epoch ms")

class InternalMessageDetail(BaseModel):
    message_id: str = Field(default_factory=lambda: str(uuid4()))
    sender_id: str = Field(..., description="UUID of the sending team member")
    sender_name: str = Field(..., description="Full name of the sending team member")
    text: str = Field(..., description="Message text content")
    message_type: str = Field(default="text", description="text, customer_chat_request, or handoff_request")
    customer_chat_request: Optional[CustomerChatRequestDetail] = Field(default=None)
    handoff_request: Optional[HandoffRequestDetail] = Field(default=None)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class InternalConversationMongo(BaseModel):
    organization_id: str = Field(..., description="References PostgreSQL Organization ID")
    type: str = Field(..., description="direct, group, or org")
    
    # Scopes
    user_ids: List[str] = Field(default_factory=list, description="For direct/group: list of participant User UUIDs")
    group_name: Optional[str] = Field(None, description="For group: Name of the group")
    group_admin_ids: List[str] = Field(default_factory=list, description="For group: Admin user IDs")
    
    messages: List[InternalMessageDetail] = Field(default_factory=list, description="Array of messages in this conversation")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = {
        "populate_by_name": True
    }
