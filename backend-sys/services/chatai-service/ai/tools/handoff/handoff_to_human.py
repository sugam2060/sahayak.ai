"""
Tool: Hand off the conversation to a human agent.
"""
import logging
from datetime import datetime, timezone
from typing import Annotated
from langchain_core.tools import tool
from langgraph.prebuilt import InjectedState
from shared.database.mongodb import MongoDBManager
from shared.kafka_producer import KafkaProducerPool

logger = logging.getLogger("chatai_service.ai.tools.handoff.handoff_to_human")


@tool
async def handoff_to_human(
    organization_id: Annotated[str, InjectedState("organization_id")],
    platform: Annotated[str, InjectedState("platform")],
    sender_id: Annotated[str, InjectedState("sender_id")],
    reason: str
) -> str:
    """Transfer the conversation to a human agent when you cannot resolve the customer's issue or the customer explicitly requests it.
    
    Args:
        organization_id: The organization's UUID (injected from state).
        platform: The platform name (injected from state).
        sender_id: The customer's platform-specific sender ID (injected from state).
        reason: Brief reason for the handoff.
    """
    try:
        db = MongoDBManager.get_db()
        
        # Find the conversation and update ai_assigned to False
        sender_id_int = int(sender_id) if str(sender_id).isdigit() else None
        query_id = {"$in": [sender_id, sender_id_int]} if sender_id_int is not None else sender_id
        
        result = await db.conversations.update_one(
            {
                "platform": platform,
                "user.sender_id": query_id
            },
            {
                "$set": {
                    "ai_assigned": False,
                    "updated_at": datetime.now(timezone.utc)
                }
            }
        )
        
        if result.modified_count == 0:
            return "Could not find the conversation to transfer. The conversation may not exist."
        
        # Publish a handoff event to notify the dashboard via WebSocket
        try:
            ws_event = {
                "org_id": organization_id,
                "platform": platform,
                "sender_id": sender_id,
                "type": "chat_handoff",
                "reason": reason,
            }
            await KafkaProducerPool.send_message("chat_websocket", ws_event)
            logger.info(f"Published handoff event for {platform}:{sender_id}")
        except Exception as e:
            logger.error(f"Failed to publish handoff event: {e}")
        
        return (
            "Conversation has been transferred to a human agent. "
            "A team member will pick up this conversation shortly."
        )
    except Exception as e:
        logger.error(f"Error during handoff: {e}", exc_info=True)
        return f"Error transferring conversation: {str(e)}"
