"""
Agent state definition for the LangGraph ReAct agent.
"""
from typing import TypedDict, Annotated, Any, Optional
from langgraph.graph.message import add_messages


class AgentState(TypedDict):
    """
    State that flows through the LangGraph ReAct agent.
    
    The `messages` field uses LangGraph's `add_messages` annotation
    which automatically manages the conversation message list — appending
    new messages and handling tool call/response pairs.
    """
    # Core message list (LangChain BaseMessage objects)
    messages: Annotated[list, add_messages]
    
    # Organization context
    organization_id: str
    organization_name: str
    
    # Platform and conversation context
    platform: str
    sender_id: str
    chat_id: str
    bot_name: str
    bot_token: str
    
    # AI configuration from organization_config_ai
    system_prompt: str
    auto_order_enabled: bool
    
    # Optional: extra context like ig_account_id
    extra: Optional[dict]
