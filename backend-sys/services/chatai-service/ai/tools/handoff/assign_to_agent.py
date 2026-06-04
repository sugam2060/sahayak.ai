"""
Tool: Assign conversation to a specific agent.
"""
import logging
from datetime import datetime, timezone
from typing import Annotated
from langchain_core.tools import tool
from langgraph.prebuilt import InjectedState
from shared.database.mongodb import MongoDBManager

logger = logging.getLogger("chatai_service.ai.tools.handoff.assign_to_agent")


@tool
async def assign_to_agent(
    organization_id: Annotated[str, InjectedState("organization_id")],
    platform: Annotated[str, InjectedState("platform")],
    sender_id: Annotated[str, InjectedState("sender_id")],
    agent_id: str,
    reason: str = ""
) -> str:
    """Assign the conversation to a specific human agent by their ID.
    
    Args:
        organization_id: The organization's UUID (injected from state).
        platform: The platform name (injected from state).
        sender_id: The customer's platform-specific sender ID (injected from state).
        agent_id: The UUID of the human agent to assign to.
        reason: Reason for the assignment.
    """
    try:
        db = MongoDBManager.get_db()
        
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
                    "assigned_user": agent_id,
                    "updated_at": datetime.now(timezone.utc)
                }
            }
        )
        
        if result.modified_count == 0:
            return "Could not find the conversation to assign."
        
        return f"Conversation assigned to agent {agent_id}. AI auto-response has been disabled."
    except Exception as e:
        logger.error(f"Error assigning to agent: {e}", exc_info=True)
        return f"Error assigning conversation: {str(e)}"
