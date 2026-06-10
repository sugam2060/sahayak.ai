import logging
from datetime import datetime, timezone
from typing import Optional, List
from uuid import uuid4
from bson import ObjectId
from shared.database.mongodb import MongoDBManager
from shared.database.schema.internal_chat_mongo import (
    InternalConversationMongo,
    InternalMessageDetail,
    CustomerChatRequestDetail
)

logger = logging.getLogger("chatai_service.internal_chat.service")

class InternalChatService:
    def __init__(self):
        pass

    @property
    def db(self):
        return MongoDBManager.get_db()

    async def get_or_create_direct_conversation(self, org_id: str, user_a: str, user_b: str) -> dict:
        """
        Retrieves or creates a 1:1 direct conversation between two users.
        """
        # Ensure user IDs are strings and sorted to prevent duplicate rooms
        sorted_users = sorted([str(user_a), str(user_b)])
        
        doc = await self.db.internal_conversations.find_one({
            "organization_id": str(org_id),
            "type": "direct",
            "user_ids": {
                "$all": sorted_users,
                "$size": 2
            }
        })
        
        if not doc:
            now = datetime.now(timezone.utc)
            convo = InternalConversationMongo(
                organization_id=str(org_id),
                type="direct",
                user_ids=sorted_users,
                group_name=None,
                group_admin_ids=[],
                messages=[],
                created_at=now,
                updated_at=now
            )
            # Create doc with custom string ID
            convo_dict = convo.model_dump(by_alias=True)
            convo_dict["_id"] = str(uuid4())
            await self.db.internal_conversations.insert_one(convo_dict)
            doc = convo_dict
        
        doc["_id"] = str(doc["_id"])
        return doc

    async def get_or_create_org_conversation(self, org_id: str) -> dict:
        """
        Retrieves or creates the single organization broadcast conversation channel.
        """
        doc = await self.db.internal_conversations.find_one({
            "organization_id": str(org_id),
            "type": "org"
        })
        
        if not doc:
            now = datetime.now(timezone.utc)
            convo = InternalConversationMongo(
                organization_id=str(org_id),
                type="org",
                user_ids=[],
                group_name="Organization Broadcast",
                group_admin_ids=[],
                messages=[],
                created_at=now,
                updated_at=now
            )
            convo_dict = convo.model_dump(by_alias=True)
            convo_dict["_id"] = f"org_{org_id}"
            await self.db.internal_conversations.insert_one(convo_dict)
            doc = convo_dict
            
        doc["_id"] = str(doc["_id"])
        return doc

    async def get_group_conversation(self, group_id: str) -> Optional[dict]:
        """
        Retrieves a group conversation by group_id.
        """
        doc = await self.db.internal_conversations.find_one({
            "_id": str(group_id),
            "type": "group"
        })
        if doc:
            doc["_id"] = str(doc["_id"])
        return doc

    async def create_group_conversation(self, org_id: str, name: str, admin_id: str, member_ids: List[str]) -> dict:
        """
        Creates a new group conversation inside organization.
        """
        now = datetime.now(timezone.utc)
        unique_members = list(set([str(admin_id)] + [str(m) for m in member_ids]))
        
        convo = InternalConversationMongo(
            organization_id=str(org_id),
            type="group",
            user_ids=unique_members,
            group_name=name,
            group_admin_ids=[str(admin_id)],
            messages=[],
            created_at=now,
            updated_at=now
        )
        convo_dict = convo.model_dump(by_alias=True)
        convo_dict["_id"] = str(uuid4())
        await self.db.internal_conversations.insert_one(convo_dict)
        convo_dict["_id"] = str(convo_dict["_id"])
        return convo_dict

    async def add_message_to_conversation(self, convo_id: str, message: InternalMessageDetail) -> None:
        """
        Appends a message detail object to an existing conversation.
        """
        now = datetime.now(timezone.utc)
        await self.db.internal_conversations.update_one(
            {"_id": convo_id},
            {
                "$push": {"messages": message.model_dump(mode="json")},
                "$set": {"updated_at": now}
            }
        )

    async def respond_to_customer_request(self, message_id: str, status: str) -> Optional[dict]:
        """
        Updates the status of a specific customer request message in the conversation.
        Returns the updated conversation document if successful.
        """
        now = datetime.now(timezone.utc)
        result = await self.db.internal_conversations.update_one(
            {"messages.message_id": message_id},
            {
                "$set": {
                    "messages.$.customer_chat_request.status": status,
                    "updated_at": now
                }
            }
        )
        if result.modified_count > 0:
            doc = await self.db.internal_conversations.find_one({"messages.message_id": message_id})
            if doc:
                doc["_id"] = str(doc["_id"])
            return doc
        return None
