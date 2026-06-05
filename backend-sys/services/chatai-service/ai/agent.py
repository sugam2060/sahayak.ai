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
from datetime import datetime, timezone
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
    logger.info(f"[Agent] run_agent: platform={platform}, sender={sender_id}, text={inbound_text!r:.80}")
    try:
        # 1. Fetch AI configuration
        ai_config = await _fetch_ai_config(org_id)
        
        if not ai_config["ai_enabled"]:
            logger.info(f"[Workflow] AI is disabled for org {org_id}. Skipping agent.")
            return None
        
        # 2. Initialize LLM
        llm = get_llm()
        mongo_db = MongoDBManager.get_db()
        thread_id = f"{platform}:{sender_id}"
        
        # Fetch customer metadata from cache
        conv = await mongo_db.conversations.find_one({"thread_id": thread_id})
        user_info = conv.get("user", {}) if conv else {}
        customer_name = user_info.get("sender_name") or user_info.get("sender_username") or ""
        
        # 3. Build the current inbound message
        content = inbound_text
        if image_url:
            content = f"{inbound_text}\n[Customer sent an image: {image_url}]" if inbound_text else f"[Customer sent an image: {image_url}]"
        
        current_message = HumanMessage(content=content)
        current_message.additional_kwargs = {
            "direction": "inbound",
            "sender_id": str(sender_id),
            "sender_name": customer_name or "Unknown",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "seen": True
        }
        
        # 4. Build and run the agent graph
        from .graph import get_agent_graph
        graph = get_agent_graph(mongo_db)
        
        config = {"configurable": {"thread_id": thread_id}}
        
        initial_state = {
            "messages": [current_message],
            "organization_id": org_id,
            "organization_name": organization_name,
            "platform": platform,
            "sender_id": str(sender_id),
            "chat_id": str(chat_id),
            "bot_name": bot_name,
            "bot_token": bot_token,
            "system_prompt": ai_config["system_prompt"],
            "auto_order_enabled": ai_config["auto_order_enabled"],
            "ai_assigned": True,
            "assigned_user": None,
            "customer_name": customer_name,
            "previous_summary": conv.get("previous_summary") if conv else None,
            "summarized_count": conv.get("summarized_count", 0) if conv else 0,
            "extra": kwargs,
        }
        logger.info(f"[Agent] Invoking graph for thread {thread_id}")
        
        result = await graph.ainvoke(initial_state, config=config)
        
        # 5. Extract the final response from the agent
        response_text = _extract_final_response(result)
        
        if not response_text:
            logger.warning("[Workflow] Agent produced no response text.")
            return None
        
        # 6. Trigger memory compaction in background (don't block the response)
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


async def test_agent_run():
    """
    Test helper function to execute run_agent with default configurations.
    """
    import sys
    import os
    # Ensure correct python path
    sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    
    from shared.database.mongodb import init_mongodb_db, MongoDBManager
    
    # Default test values (can be customized)
    test_org_id = "de851b5f-b375-4942-862a-3a9406a2f1da"
    test_platform = "telegram"
    test_sender_id = "9999"
    test_chat_id = "8888"
    test_bot_name = "TestBot"
    test_bot_token = "mock-token"
    test_inbound_text = "I want to buy a headset so place the order, my phone no is: 9801234567 and location is Bagbazar"
    
    print("Initializing MongoDB indexes...")
    await init_mongodb_db()
    
    print(f"Running agent for org: {test_org_id}, message: {test_inbound_text!r}...")
    try:
        response = await run_agent(
            org_id=test_org_id,
            platform=test_platform,
            sender_id=test_sender_id,
            chat_id=test_chat_id,
            bot_name=test_bot_name,
            bot_token=test_bot_token,
            inbound_text=test_inbound_text
        )
        print("=" * 40)
        print("Agent Response:", response)
        print("=" * 40)
    finally:
        await MongoDBManager.close()

if __name__ == "__main__":
    import asyncio
    asyncio.run(test_agent_run())
