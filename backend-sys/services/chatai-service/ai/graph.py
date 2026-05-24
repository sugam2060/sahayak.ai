import os
import logging
from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import ToolNode
from shared.database.schema.chat_message_mongo import MessageIntent
from shared.config import MONGODB_URL, MONGODB_DB_NAME
from langgraph.checkpoint.mongodb import MongoDBSaver

from .state import CustomerState
from .agents.intent_extractor import extract_intent_node
from .agents.sales_agent import sales_agent_node
from .agents.support_agent import support_agent_node
from .embeddings import search_semantic_context
from .tools.db_tools import lookup_products, check_product_availability
from .tools.handoff_tool import request_human_handoff
from shared.database.mongodb import MongoDBManager
from shared.kafka_producer import KafkaProducerPool

logger = logging.getLogger("chatai_service.graph")

async def rag_retriever_node(state: CustomerState) -> dict:
    """
    Parallel context retrieval node. Searches RAG store for relevant history.
    """
    messages = state.get("messages", [])
    if not messages:
        return {"retrieved_context": []}
    
    last_user_message = messages[-1].content
    sender_id = state.get("sender_id")
    platform = state.get("platform", "telegram")
    
    context = await search_semantic_context(sender_id, platform, last_user_message, limit=3)
    return {"retrieved_context": context}

async def join_node(state: CustomerState) -> dict:
    """
    No-op node acting as a sync barrier for intent_extractor and rag_retriever.
    """
    return {}

async def handoff_node(state: CustomerState) -> dict:
    """
    Handoff node. Updates MongoDB, posts Kafka WebSocket event, and generates handoff message.
    """
    sender_id = state.get("sender_id")
    platform = state.get("platform", "telegram")
    org_id = state.get("organization_id")
    
    logger.info(f"Executing handoff_node for sender_id: {sender_id} ({platform})")
    
    try:
        db = MongoDBManager.get_db()
        await db.conversations.update_one(
            {
                "platform": platform.lower(),
                "user.sender_id": sender_id
            },
            {
                "$set": {
                    "ai_assigned": False
                }
            }
        )
    except Exception as e:
        logger.error(f"Failed to update MongoDB ai_assigned flag during handoff: {e}")
        
    try:
        ws_event = {
            "org_id": str(org_id),
            "platform": platform.lower(),
            "sender_id": sender_id,
            "type": "ai_assigned_toggle",
            "ai_assigned": False
        }
        await KafkaProducerPool.send_message("chat_websocket", ws_event)
        logger.info(f"Published ai_assigned_toggle = False to Kafka chat_websocket for org: {org_id}")
    except Exception as e:
        logger.error(f"Failed to publish Kafka handoff websocket toggle: {e}")
        
    from langchain_core.messages import AIMessage
    return {
        "messages": [AIMessage(content="I have notified a human agent to take over this conversation. They will get back to you shortly!")],
        "handoff_requested": True
    }

def route_by_intent(state: CustomerState) -> str:
    """
    Determine whether to route to sales agent, support agent, or human handoff.
    """
    if state.get("handoff_requested"):
        return "handoff_agent"
        
    messages = state.get("messages", [])
    if messages:
        last_msg = messages[-1].content.lower()
        if any(kw in last_msg for kw in ["human", "agent", "person", "representative", "talk to human"]):
            return "handoff_agent"
            
    intent = state.get("intent")
    if intent == MessageIntent.BUY:
        return "sales_agent"
    return "support_agent"

def route_sales_agent_output(state: CustomerState) -> str:
    """
    Route sales agent output: to tools node, handoff node, or END.
    """
    messages = state.get("messages", [])
    if not messages:
        return END
    last_msg = messages[-1]
    
    if hasattr(last_msg, "tool_calls") and last_msg.tool_calls:
        for tc in last_msg.tool_calls:
            if tc["name"] == "request_human_handoff":
                return "handoff_agent"
        return "sales_tools"
        
    if state.get("handoff_requested"):
        return "handoff_agent"
        
    return END

def route_support_agent_output(state: CustomerState) -> str:
    """
    Route support agent output: to tools node, handoff node, or END.
    """
    messages = state.get("messages", [])
    if not messages:
        return END
    last_msg = messages[-1]
    
    if hasattr(last_msg, "tool_calls") and last_msg.tool_calls:
        for tc in last_msg.tool_calls:
            if tc["name"] == "request_human_handoff":
                return "handoff_agent"
        return "support_tools"
        
    if state.get("handoff_requested"):
        return "handoff_agent"
        
    return END

# Build StateGraph
builder = StateGraph(CustomerState)

# Add Nodes
builder.add_node("intent_extractor", extract_intent_node)
builder.add_node("rag_retriever", rag_retriever_node)
builder.add_node("join_node", join_node)
builder.add_node("sales_agent", sales_agent_node)
builder.add_node("support_agent", support_agent_node)
builder.add_node("handoff_agent", handoff_node)

# Add Tool Nodes
sales_tools_node = ToolNode([lookup_products, check_product_availability])
support_tools_node = ToolNode([request_human_handoff])
builder.add_node("sales_tools", sales_tools_node)
builder.add_node("support_tools", support_tools_node)

# Add Parallel Flows from START
builder.add_edge(START, "intent_extractor")
builder.add_edge(START, "rag_retriever")

# Join parallel paths
builder.add_edge("intent_extractor", "join_node")
builder.add_edge("rag_retriever", "join_node")

# Conditional routing from join_node
builder.add_conditional_edges(
    "join_node",
    route_by_intent,
    {
        "sales_agent": "sales_agent",
        "support_agent": "support_agent",
        "handoff_agent": "handoff_agent"
    }
)

# Conditional routing from sales_agent
builder.add_conditional_edges(
    "sales_agent",
    route_sales_agent_output,
    {
        "sales_tools": "sales_tools",
        "handoff_agent": "handoff_agent",
        END: END
    }
)

# Conditional routing from support_agent
builder.add_conditional_edges(
    "support_agent",
    route_support_agent_output,
    {
        "support_tools": "support_tools",
        "handoff_agent": "handoff_agent",
        END: END
    }
)

# Tool loopbacks
builder.add_edge("sales_tools", "sales_agent")
builder.add_edge("support_tools", "support_agent")

# Handoff node goes directly to END
builder.add_edge("handoff_agent", END)

# Export async caller
async def invoke_customer_handling_graph(
    org_id: str,
    platform: str,
    sender_id: int,
    bot_name: str,
    chat_id: int,
    user_message: str
) -> str:
    """
    Compile the LangGraph on the fly using a MongoDB checkpointer connection context,
    invoke the state machine, and return the final AI message content.
    """
    thread_id = f"{platform.lower()}_{sender_id}"
    config = {"configurable": {"thread_id": thread_id}}
    
    input_state = {
        "messages": [("user", user_message)],
        "intent": MessageIntent.NO_INTENT,
        "customer_info": {},
        "organization_id": org_id,
        "bot_name": bot_name,
        "chat_id": chat_id,
        "sender_id": sender_id,
        "retrieved_context": [],
        "catalog_context": [],
        "handoff_requested": False
    }
    
    with MongoDBSaver.from_conn_string(MONGODB_URL, db_name=MONGODB_DB_NAME) as checkpointer:
        app = builder.compile(checkpointer=checkpointer)
        output_state = await app.ainvoke(input_state, config=config)
        final_messages = output_state.get("messages", [])
        if final_messages:
            return str(final_messages[-1].content)
            
    return "I'm here to help. How can I assist you?"
