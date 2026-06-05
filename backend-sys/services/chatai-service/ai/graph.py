"""
LangGraph ReAct agent graph definition.

Implements the classic ReAct loop:
  START → agent_node → should_continue? → tool_node → agent_node (loop)
                                        → END (if no tool calls)
"""
import logging
from datetime import datetime, timezone
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from langchain_core.messages import AIMessage

from .state import AgentState
from .memory import build_system_message

logger = logging.getLogger("chatai_service.ai.graph")


def _should_continue(state: AgentState) -> str:
    """
    Conditional edge: checks if the last AI message contains tool calls.
    If yes → route to 'tools' node. If no → END the graph.
    """
    messages = state.get("messages", [])
    if not messages:
        return END
    last_message = messages[-1]
    
    # If the LLM returned tool calls, continue to tool execution
    if isinstance(last_message, AIMessage) and last_message.tool_calls:
        return "tools"
    
    # Otherwise, we're done — the agent has produced a final response
    return END


def build_agent_graph(tools: list, llm, checkpointer=None):
    """
    Build and compile a LangGraph StateGraph implementing the ReAct pattern.
    
    Args:
        tools: List of LangChain tool objects to bind to the LLM.
        llm: The LLM instance (ChatNVIDIA) to use for reasoning.
        checkpointer: Optional checkpointer instance to persist graph state.
    
    Returns:
        A compiled LangGraph StateGraph ready for invocation.
    """
    # Bind tools to the LLM so it can generate tool_calls
    llm_with_tools = llm.bind_tools(tools)
    
    async def agent_node(state: AgentState) -> dict:
        """
        The reasoning node: calls the LLM with the current message history.
        The LLM will either produce a text response or tool call(s).
        """
        messages = state["messages"]
        # Only pass the last 5 messages to the LLM to keep context window small and efficient
        recent_messages = messages[-5:] if len(messages) > 5 else messages
        system_msg = build_system_message(
            system_prompt=state.get("system_prompt", ""),
            previous_summary=state.get("previous_summary"),
            platform=state.get("platform", ""),
            bot_name=state.get("bot_name", ""),
            auto_order_enabled=state.get("auto_order_enabled", False)
        )
        response = await llm_with_tools.ainvoke([system_msg] + recent_messages)
        response.additional_kwargs = {
            "direction": "outbound",
            "sender_id": 0,
            "sender_name": state.get("bot_name", "AI Assistant"),
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        return {"messages": [response]}
    
    # Create the tool execution node using LangGraph's prebuilt ToolNode
    tool_node = ToolNode(tools)
    
    # Build the graph
    graph = StateGraph(AgentState)
    
    # Add nodes
    graph.add_node("agent", agent_node)
    graph.add_node("tools", tool_node)
    
    # Set the entry point
    graph.set_entry_point("agent")
    
    # Add conditional edges from agent node
    graph.add_conditional_edges(
        "agent",
        _should_continue,
        {
            "tools": "tools",
            END: END
        }
    )
    
    # After tool execution, always go back to agent for reasoning
    graph.add_edge("tools", "agent")
    
    # Compile and return
    compiled = graph.compile(checkpointer=checkpointer)
    logger.debug("ReAct agent graph compiled successfully.")
    return compiled


def get_agent_graph(db):
    """
    Helper function to load LLM, tools, and return compiled graph with checkpointer.
    """
    from .llm import get_llm
    from .tools import get_all_tools
    from .mongodb_checkpoint import AsyncMongoDBSaver
    
    checkpointer = AsyncMongoDBSaver(db)
    tools = get_all_tools()
    llm = get_llm()
    return build_agent_graph(tools=tools, llm=llm, checkpointer=checkpointer)

