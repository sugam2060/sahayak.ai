"""
Tool: Check if human agents are available.
Stub implementation — can be expanded with real agent presence tracking.
"""
import logging
from typing import Annotated
from langchain_core.tools import tool
from langgraph.prebuilt import InjectedState

logger = logging.getLogger("chatai_service.ai.tools.handoff.check_agent_availability")


@tool
async def check_agent_availability(
    organization_id: Annotated[str, InjectedState("organization_id")]
) -> str:
    """Check if human agents are currently available to handle conversations.
    
    Args:
        organization_id: The organization's UUID (injected from state).
    """
    # Stub: always returns available
    # TODO: Implement real availability check (e.g., check online agents in DB/Redis)
    return (
        "Human agents are available. "
        "You can use the handoff_to_human tool to transfer the conversation."
    )
