"""
Main entry point for the AI agent.

Orchestrates:
1. Fetching organization AI config (system prompt, flags)
2. Syncing human/recent messages from MongoDB conversation history to checkpointer
3. Running the compiled LangGraph checkpointer state graph
4. Extracting final response and image URLs
"""
import logging
from typing import Optional, Union, Dict, Any
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage

from shared.database.mongodb import MongoDBManager
from shared.database.engine import SessionLocal
from shared.database.schema.organization_config_ai import OrganizationConfigAI
from sqlalchemy import select
from uuid import UUID

from .llm import LLMProvider
from .graph import build_agent_graph
from .tools import get_all_tools
from .event_emitter import AIEventEmitter

logger = logging.getLogger("chatai_service.ai.agent")


async def _fetch_ai_config(org_id: str) -> dict:
    """
    Fetch the organization's AI configuration from PostgreSQL.
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
) -> Optional[dict]:
    """
    Run the AI agent using LangGraph checkpointing.
    
    Returns:
        dict: {"text": "...", "image_urls": ["..."]} or None
    """
    try:
        # 1. Fetch AI configuration
        ai_config = await _fetch_ai_config(org_id)
        
        if not ai_config["ai_enabled"]:
            logger.debug(f"AI is disabled for org {org_id}. Skipping agent.")
            return None
        
        # 2. Get LLM and Tools
        llm = LLMProvider.get_reasoning_model()
        tools = get_all_tools()
        
        # 3. Setup Checkpointer (Synchronous MongoClient for MongoDBSaver)
        from pymongo import MongoClient
        from langgraph.checkpoint.mongodb import MongoDBSaver
        from shared.config import MONGODB_URL, MONGODB_DB_NAME
        
        sync_client = MongoClient(MONGODB_URL)
        saver = MongoDBSaver(
            client=sync_client,
            db_name=MONGODB_DB_NAME,
            checkpoint_collection_name="agent_checkpoints",
            writes_collection_name="agent_checkpoint_writes"
        )
        
        # Compile graph with saver
        graph = build_agent_graph(tools=tools, llm=llm, checkpointer=saver)
        
        # Dynamic Thread ID format: [platform]+[chat_id]+[sender_id]
        thread_id = f"{platform}+{chat_id}+{sender_id}"
        config = {"configurable": {"thread_id": thread_id}}
        
        # 4. Fetch state snapshot from saver
        state_snapshot = await graph.aget_state(config)
        existing_messages = state_snapshot.values.get("messages", []) if state_snapshot.values else []
        
        # 5. Fetch human & recent conversation history from MongoDB
        mongo_db = MongoDBManager.get_db()
        sender_id_int = int(sender_id) if str(sender_id).isdigit() else None
        query_id = {"$in": [sender_id, sender_id_int]} if sender_id_int is not None else sender_id
        
        conv = await mongo_db.conversations.find_one({
            "platform": platform,
            "user.sender_id": query_id
        })
        mongo_messages = conv.get("messages", []) if conv else []
        
        # Find the last AIMessage or HumanMessage in checkpointer
        last_existing = None
        for m in reversed(existing_messages):
            if isinstance(m, (HumanMessage, AIMessage)) and not isinstance(m, SystemMessage):
                last_existing = m
                break
                
        # Find alignment index in MongoDB messages
        sync_index = -1
        if last_existing:
            for idx, msg in enumerate(mongo_messages):
                direction = msg.get("direction", "inbound")
                expected_role = "inbound" if isinstance(last_existing, HumanMessage) else "outbound"
                msg_content = msg.get("text", "")
                if msg.get("image_url"):
                    msg_content = f"{msg_content}\n[Customer sent an image: {msg.get('image_url')}]" if msg_content else f"[Customer sent an image: {msg.get('image_url')}]"
                if direction == expected_role and msg_content.strip() == last_existing.content.strip():
                    sync_index = idx
                    
        # Extract unsynced human and newer messages
        messages_to_sync = mongo_messages[sync_index + 1:] if sync_index != -1 else mongo_messages
        new_langchain_messages = []
        for msg in messages_to_sync:
            direction = msg.get("direction", "inbound")
            text = msg.get("text", "")
            img_u = msg.get("image_url")
            content = text
            if img_u:
                content = f"{text}\n[Customer sent an image: {img_u}]" if text else f"[Customer sent an image: {img_u}]"
            if direction == "inbound":
                new_langchain_messages.append(HumanMessage(content=content))
            else:
                new_langchain_messages.append(AIMessage(content=content))
                
        # 6. Retrieve stored CRM details
        customer_phone = None
        customer_address = None
        try:
            from shared.database.schema.customers import Customer
            from shared.database.schema.orders import PlatformType
            
            platform_enum = PlatformType(platform.lower())
            async with SessionLocal() as session:
                cust_stmt = select(Customer).where(
                    Customer.organization_id == UUID(org_id),
                    Customer.platform == platform_enum,
                    Customer.external_id == str(sender_id)
                )
                cust_res = await session.execute(cust_stmt)
                cust = cust_res.scalars().first()
                if cust:
                    customer_phone = cust.phone
                    customer_address = cust.delivery_address
        except Exception as e:
            logger.error(f"Error fetching customer from PostgreSQL: {e}", exc_info=True)

        user_info = conv.get("user", {}) if conv else {}
        customer_name = user_info.get("sender_name") or user_info.get("sender_username") or ""

        # Initialize invocation state
        initial_state = {
            "messages": new_langchain_messages,
            "organization_id": org_id,
            "organization_name": organization_name,
            "platform": platform,
            "sender_id": str(sender_id),
            "chat_id": str(chat_id),
            "bot_name": bot_name,
            "bot_token": bot_token,
            "system_prompt": ai_config["system_prompt"],
            "auto_order_enabled": ai_config["auto_order_enabled"],
            "customer_name": customer_name,
            "extra": {
                "customer_phone": customer_phone,
                "customer_address": customer_address,
                **kwargs
            },
            "image_urls": [], # Reset image URLs for this run
            "products": [] # Reset products for this run
        }
        
        # Emit processing started event
        await AIEventEmitter.emit(
            org_id=org_id,
            platform=platform,
            sender_id=sender_id,
            event="processing",
            status="started"
        )

        aborted = False
        async for _ in graph.astream(initial_state, config=config):
            # Check MongoDB for conversation to see if AI auto reply was turned off mid-run
            conv_status = await mongo_db.conversations.find_one({
                "platform": platform,
                "user.sender_id": query_id
            }, projection={"ai_assigned": 1})
            
            if conv_status and not conv_status.get("ai_assigned", False):
                aborted = True
                logger.info(f"AI auto reply disabled mid-processing for {platform}:{sender_id}. Aborting.")
                break

        if aborted:
            await AIEventEmitter.emit(
                org_id=org_id,
                platform=platform,
                sender_id=sender_id,
                event="aborted",
                status="completed"
            )
            return None

        # Fetch the final state after stream finishes
        final_state_snapshot = await graph.aget_state(config)
        result = final_state_snapshot.values or {}

        # Emit processing completed event
        await AIEventEmitter.emit(
            org_id=org_id,
            platform=platform,
            sender_id=sender_id,
            event="processing",
            status="completed"
        )
        
        # Extract response text and image URLs
        response_text = _extract_final_response(result)
        image_urls = result.get("image_urls") or []
        products = result.get("products") or []
        
        logger.info(f"Agent response for {platform}:{sender_id}: {response_text[:100] if response_text else 'None'}...")
        return {
            "text": response_text,
            "image_urls": image_urls,
            "products": products
        }
        
    except Exception as e:
        logger.error(f"Error running AI agent for {platform}:{sender_id}: {e}", exc_info=True)
        return None


def _extract_final_response(result: dict) -> Optional[str]:
    """
    Extract the final text response from the LangGraph result.
    """
    messages = result.get("messages", [])
    if not messages:
        return None
    
    for msg in reversed(messages):
        if hasattr(msg, "tool_calls") and msg.tool_calls:
            continue
        if hasattr(msg, "content") and msg.content:
            if hasattr(msg, "type") and msg.type == "tool":
                continue
            if isinstance(msg, SystemMessage):
                continue
            return msg.content
    
    return None


async def test_agent_run():
    """
    Test helper function.
    """
    from shared.database.mongodb import init_mongodb_db
    
    test_org_id = "de851b5f-b375-4942-862a-3a9406a2f1da"
    test_platform = "telegram"
    test_sender_id = "9999"
    test_chat_id = "8888"
    test_bot_name = "TestBot"
    test_bot_token = "mock-token"
    test_inbound_text = "I want to see the product details of a product with ID a77dd5e2-3b76-4460-b40a-76915db88acb"
    
    print("Initializing MongoDB...")
    await init_mongodb_db()
    
    print(f"Running agent for org: {test_org_id}...")
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
        print("Agent Response Dict:", response)
        print("=" * 40)
    finally:
        await MongoDBManager.close()

if __name__ == "__main__":
    import asyncio
    asyncio.run(test_agent_run())

