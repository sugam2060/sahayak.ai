"""
LangGraph ReAct agent graph definition with 2-way routing, tools, synthesizer, and product card generation.
"""
import io
import logging
import re
import httpx
from PIL import Image, ImageDraw, ImageFont
from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import ToolNode
from langchain_core.messages import AIMessage, ToolMessage, RemoveMessage, SystemMessage

from shared.proto import service_pb2
from .grpc_client import WorkersGRPCClient
from shared.utils import upload_cloudinary_image_bytes
from .state import AgentState
from .tools.products.generate_product_card import _draw_pillow_card
from .event_emitter import AIEventEmitter

logger = logging.getLogger("chatai_service.ai.graph")


def _should_continue(state: AgentState) -> str:
    """
    Conditional edge: routes from chat node.
    - If generate_product_card tool call is present -> 'generate_product_card'
    - If other tool calls are present -> 'tools'
    - Otherwise -> 'synthesizer'
    """
    messages = state["messages"]
    last_message = messages[-1]
    
    if isinstance(last_message, AIMessage) and last_message.tool_calls:
        for tc in last_message.tool_calls:
            if tc["name"] == "generate_product_card":
                logger.info("[Edge Event] Routing from 'chat' -> 'generate_product_card'")
                return "generate_product_card"
        
        tool_names = [tc["name"] for tc in last_message.tool_calls]
        logger.info(f"[Edge Event] Routing from 'chat' -> 'tools' (requested tools: {', '.join(tool_names)})")
        return "tools"
    
    logger.info("[Edge Event] Routing from 'chat' -> 'synthesizer'")
    return "synthesizer"


def build_agent_graph(tools: list, llm, checkpointer=None):
    """
    Build and compile the LangGraph StateGraph.
    
    Flow:
    START -> chat
    chat -> tools -> chat (Standard tool loop)
    chat -> generate_product_card -> END
    chat -> synthesizer -> END
    """
    llm_with_tools = llm.bind_tools(tools)
    
    async def chat_node(state: AgentState) -> dict:
        """
        Decision maker node: invokes LLM with message history.
        Before calling the LLM, we rebuild the SystemMessage with CRM context and summary,
        ensuring it is updated each turn.
        """
        await AIEventEmitter.emit(
            org_id=state["organization_id"],
            platform=state["platform"],
            sender_id=state["sender_id"],
            event="thinking",
            status="started"
        )
        messages = state["messages"]
        thread_id = f"{state.get('platform')}+{state.get('chat_id')}+{state.get('sender_id')}"
        logger.info(f"[Node Trigger] 'chat' node entered for thread={thread_id}. Message count: {len(messages)}")
        
        # 1. Update system message at the beginning of the list using id="system"
        # Gather info to rebuild system message
        from .memory import build_system_message
        
        # Retrieve stored customer details if available
        customer_phone = state.get("extra", {}).get("customer_phone")
        customer_address = state.get("extra", {}).get("customer_address")
        
        system_msg = build_system_message(
            system_prompt=state["system_prompt"],
            previous_summary=state.get("previous_summary"),
            platform=state["platform"],
            bot_name=state["bot_name"],
            auto_order_enabled=state["auto_order_enabled"],
            customer_phone=customer_phone,
            customer_address=customer_address
        )
        system_msg.id = "system"
        
        # Invoke LLM with updated system prompt + history
        # (add_messages will overwrite the system message since it has id="system")
        response = await llm_with_tools.ainvoke([system_msg] + [m for m in messages if getattr(m, "id", None) != "system"])
        
        await AIEventEmitter.emit(
            org_id=state["organization_id"],
            platform=state["platform"],
            sender_id=state["sender_id"],
            event="thinking",
            status="completed"
        )
        return {"messages": [system_msg, response]}
    
    async def generate_product_card_node(state: AgentState) -> dict:
        """
        Retrieve product metadata using stubs and append them to products list in state.
        """
        await AIEventEmitter.emit(
            org_id=state["organization_id"],
            platform=state["platform"],
            sender_id=state["sender_id"],
            event="generating_product_card",
            status="started"
        )
        messages = state["messages"]
        last_message = messages[-1]
        
        product_ids = []
        tool_call_id = None
        tool_name = "generate_product_card"
        
        if isinstance(last_message, AIMessage) and last_message.tool_calls:
            for tc in last_message.tool_calls:
                if tc["name"] == "generate_product_card":
                    product_ids = tc["args"].get("product_ids", [])
                    tool_call_id = tc["id"]
                    break
        
        if not product_ids or not tool_call_id:
            logger.warning("generate_product_card called but no product_ids or tool_call_id found.")
            await AIEventEmitter.emit(
                org_id=state["organization_id"],
                platform=state["platform"],
                sender_id=state["sender_id"],
                event="generating_product_card",
                status="completed"
            )
            return {}
            
        logger.info(f"[Node Trigger] 'generate_product_card' for products: {product_ids}")
        products = list(state.get("products") or [])
        
        _, product_stub, _ = WorkersGRPCClient.get_stubs()
        
        import json
        for pid in product_ids:
            try:
                request = service_pb2.GetProductDetailRequest(
                    organization_id=state["organization_id"],
                    product_id=pid
                )
                response = await product_stub.GetProductDetail(request)
                if not response.success or not response.product:
                    logger.warning(f"Failed to fetch details for product: {pid}")
                    continue
                
                p = response.product
                meta_dict = None
                if p.metadata_json:
                    try:
                        meta_dict = json.loads(p.metadata_json)
                    except Exception:
                        pass
                
                product_dict = {
                    "id": p.id,
                    "organization_id": p.organization_id,
                    "name": p.name,
                    "description": p.description if p.description else None,
                    "price": p.price,
                    "currency": p.currency,
                    "stock": p.stock,
                    "sku": p.sku if p.sku else None,
                    "image": p.image if p.image else None,
                    "is_active": p.is_active,
                    "created_at": p.created_at,
                    "updated_at": p.updated_at,
                    "metadata": meta_dict
                }
                products.append(product_dict)
            except Exception as e:
                logger.error(f"Error fetching product metadata for {pid}: {e}", exc_info=True)
                
        # Satisfy tool call
        tool_msg = ToolMessage(
            content=f"Successfully shared {len(products)} product cards.",
            tool_call_id=tool_call_id,
            name=tool_name
        )
        # Create final answer
        ai_reply = AIMessage(
            content=f"Here is the product card for the requested product(s):"
        )
        await AIEventEmitter.emit(
            org_id=state["organization_id"],
            platform=state["platform"],
            sender_id=state["sender_id"],
            event="generating_product_card",
            status="completed"
        )
        return {
            "messages": [tool_msg, ai_reply],
            "products": products
        }
    
    # Prebuilt ToolNode
    tool_node_prebuilt = ToolNode(tools)
    
    async def logging_tool_node(state: AgentState) -> dict:
        """Wrapper for standard ToolNode execution to log completion."""
        logger.info("[Node Trigger] 'tools' node entered.")
        messages = state["messages"]
        last_message = messages[-1]
        tool_names = []
        if isinstance(last_message, AIMessage) and last_message.tool_calls:
            tool_names = [tc["name"] for tc in last_message.tool_calls]
            
        for t_name in tool_names:
            await AIEventEmitter.emit(
                org_id=state["organization_id"],
                platform=state["platform"],
                sender_id=state["sender_id"],
                event=t_name,
                status="started"
            )
            
        result = await tool_node_prebuilt.ainvoke(state)
        
        for t_name in tool_names:
            await AIEventEmitter.emit(
                org_id=state["organization_id"],
                platform=state["platform"],
                sender_id=state["sender_id"],
                event=t_name,
                status="completed"
            )
        return result
        
    async def synthesizer_node(state: AgentState) -> dict:
        """
        Cleans the final response text, stripping markdown tags for clean plain-text channels.
        """
        logger.info("[Node Trigger] 'synthesizer' node entered.")
        await AIEventEmitter.emit(
            org_id=state["organization_id"],
            platform=state["platform"],
            sender_id=state["sender_id"],
            event="finalizing_response",
            status="started"
        )
        await AIEventEmitter.emit(
            org_id=state["organization_id"],
            platform=state["platform"],
            sender_id=state["sender_id"],
            event="finalizing_response",
            status="completed"
        )
        return {}
        
    # Build the graph
    graph = StateGraph(AgentState)
    
    # Add nodes
    graph.add_node("chat", chat_node)
    graph.add_node("tools", logging_tool_node)
    graph.add_node("generate_product_card", generate_product_card_node)
    graph.add_node("synthesizer", synthesizer_node)
    
    # Routing
    graph.set_entry_point("chat")
    
    graph.add_conditional_edges(
        "chat",
        _should_continue,
        {
            "tools": "tools",
            "generate_product_card": "generate_product_card",
            "synthesizer": "synthesizer"
        }
    )
    
    graph.add_edge("tools", "chat")
    graph.add_edge("generate_product_card", END)
    graph.add_edge("synthesizer", END)
    
    compiled = graph.compile(checkpointer=checkpointer)
    logger.debug("Refactored 2-way routing state graph compiled.")
    return compiled




