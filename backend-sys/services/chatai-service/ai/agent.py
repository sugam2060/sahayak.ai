"""
Main entry point for the AI agent.

Orchestrates:
1. Fetching organization AI config (system prompt, flags)
2. Loading conversation history from MongoDB
3. Building tools and the LangGraph ReAct agent
4. Running the agent and extracting the response
5. Triggering memory compaction (10:5 strategy)
"""
import logging
from typing import Optional
from langchain_core.messages import HumanMessage

from shared.database.mongodb import MongoDBManager
from shared.database.engine import SessionLocal
from shared.database.schema.organization_config_ai import OrganizationConfigAI
from sqlalchemy import select
from uuid import UUID

from .llm import get_llm, get_summary_llm
from .memory import (
    load_conversation_memory,
    maybe_summarize_and_compact,
    build_system_message,
)
from .graph import build_agent_graph
from .tools import get_all_tools

logger = logging.getLogger("chatai_service.ai.agent")


async def _fetch_ai_config(org_id: str) -> dict:
    """
    Fetch the organization's AI configuration from PostgreSQL.
    
    Returns a dict with: ai_enabled, auto_order_enabled, system_prompt, knowledge_base
    """
    try:
        async with SessionLocal() as db:
            stmt = select(OrganizationConfigAI).where(
                OrganizationConfigAI.organization_id == UUID(org_id)
            )
            res = await db.execute(stmt)
            config = res.scalar_one_or_none()
            
            if not config:
                logger.warning(f"No AI config found for org {org_id}. Using defaults.")
                return {
                    "ai_enabled": False,
                    "auto_order_enabled": False,
                    "system_prompt": "You are a helpful assistant.",
                    "knowledge_base": "",
                }
            
            return {
                "ai_enabled": config.ai_enabled,
                "auto_order_enabled": config.auto_order_enabled,
                "system_prompt": config.system_prompt or "You are a helpful assistant.",
                "knowledge_base": config.knowledge_base or "",
            }
    except Exception as e:
        logger.error(f"Error fetching AI config for org {org_id}: {e}", exc_info=True)
        return {
            "ai_enabled": False,
            "auto_order_enabled": False,
            "system_prompt": "You are a helpful assistant.",
            "knowledge_base": "",
        }


async def run_agent(
    org_id: str,
    platform: str,
    sender_id,
    chat_id,
    bot_name: str,
    bot_token: str,
    inbound_text: str,
    image_url: Optional[str] = None,
    organization_name: str = "",
    **kwargs
) -> Optional[str]:
    """
    Run the AI agent for an inbound customer message.
    
    This is the main entry point called from platform handlers after
    saving the inbound message to MongoDB.
    
    Args:
        org_id: Organization UUID string
        platform: Platform name (telegram, instagram)
        sender_id: Customer's platform-specific sender ID
        chat_id: Platform chat/conversation ID
        bot_name: Name of the bot
        bot_token: Bot authentication token
        inbound_text: The customer's message text
        image_url: Optional image URL from the message
        organization_name: Organization name for context
        **kwargs: Extra fields (e.g., ig_account_id)
    
    Returns:
        The AI agent's response text, or None if the agent shouldn't respond.
    """
    try:
        # 1. Fetch AI configuration
        ai_config = await _fetch_ai_config(org_id)
        
        if not ai_config["ai_enabled"]:
            logger.debug(f"AI is disabled for org {org_id}. Skipping agent.")
            return None
        
        # 2. Initialize LLM
        llm = get_llm()
        
        # 3. Load conversation history from MongoDB
        mongo_db = MongoDBManager.get_db()
        history_messages, previous_summary = await load_conversation_memory(
            db=mongo_db,
            platform=platform,
            sender_id=sender_id
        )
        
        # 4. Build system message
        system_msg = build_system_message(
            system_prompt=ai_config["system_prompt"],
            previous_summary=previous_summary,
            platform=platform,
            bot_name=bot_name,
            auto_order_enabled=ai_config["auto_order_enabled"]
        )
        
        # 5. Build the current inbound message
        content = inbound_text
        if image_url:
            content = f"{inbound_text}\n[Customer sent an image: {image_url}]" if inbound_text else f"[Customer sent an image: {image_url}]"
        
        current_message = HumanMessage(content=content)
        
        # 6. Assemble the full message list: system + history + current
        # Note: history_messages already exclude the current inbound (it was just saved)
        # We remove the last message from history if it matches the current inbound
        # to avoid duplication (since the handler saves before calling us)
        if history_messages and history_messages[-1].content == current_message.content:
            history_messages = history_messages[:-1]
        
        all_messages = [system_msg] + history_messages + [current_message]
        
        # 7. Build tools
        tools = get_all_tools()
        
        # 8. Build and run the agent graph
        graph = build_agent_graph(tools=tools, llm=llm)
        
        initial_state = {
            "messages": all_messages,
            "organization_id": org_id,
            "organization_name": organization_name,
            "platform": platform,
            "sender_id": str(sender_id),
            "chat_id": str(chat_id),
            "bot_name": bot_name,
            "bot_token": bot_token,
            "system_prompt": ai_config["system_prompt"],
            "auto_order_enabled": ai_config["auto_order_enabled"],
            "extra": kwargs,
        }
        
        result = await graph.ainvoke(initial_state)
        
        # 9. Extract the final response from the agent
        response_text = _extract_final_response(result)
        
        if not response_text:
            logger.warning("Agent produced no response text.")
            return None
        
        # 10. Trigger memory compaction in background (don't block the response)
        try:
            summary_llm = get_summary_llm()
            await maybe_summarize_and_compact(
                db=mongo_db,
                platform=platform,
                sender_id=sender_id,
                llm=summary_llm
            )
        except Exception as e:
            logger.error(f"Memory compaction failed (non-critical): {e}", exc_info=True)
        
        logger.info(f"Agent response for {platform}:{sender_id}: {response_text[:100]}...")
        return response_text
        
    except Exception as e:
        logger.error(f"Error running AI agent for {platform}:{sender_id}: {e}", exc_info=True)
        return None


def _extract_final_response(result: dict) -> Optional[str]:
    """
    Extract the final text response from the LangGraph result.
    The last message should be an AIMessage without tool calls.
    """
    messages = result.get("messages", [])
    if not messages:
        return None
    
    # Walk backwards to find the last AIMessage without tool calls
    for msg in reversed(messages):
        if hasattr(msg, "tool_calls") and msg.tool_calls:
            continue
        if hasattr(msg, "content") and msg.content:
            # Skip tool response messages
            if hasattr(msg, "type") and msg.type == "tool":
                continue
            return msg.content
    
    return None
