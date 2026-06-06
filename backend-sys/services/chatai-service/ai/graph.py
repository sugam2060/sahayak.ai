"""
LangGraph ReAct agent graph definition.

Implements the classic ReAct loop:
  START → agent_node → should_continue? → tool_node → agent_node (loop)
                                        → END (if no tool calls)
"""
import logging
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from langchain_core.messages import AIMessage

from .state import AgentState

logger = logging.getLogger("chatai_service.ai.graph")


def _should_continue(state: AgentState) -> str:
    """
    Conditional edge: checks if the last AI message contains tool calls.
    If yes → route to 'tools' node. If no → END the graph.
    """
    messages = state["messages"]
    last_message = messages[-1]
    
    # If the LLM returned tool calls, continue to tool execution
    if isinstance(last_message, AIMessage) and last_message.tool_calls:
        tool_names = [tc["name"] for tc in last_message.tool_calls]
        logger.info(f"[Edge Event] Routing from 'agent' -> 'tools' (requested tools: {', '.join(tool_names)})")
        return "tools"
    
    # Otherwise, we're done — the agent has produced a final response
    logger.info("[Edge Event] Routing from 'agent' -> END")
    return END


def build_agent_graph(tools: list, llm):
    """
    Build and compile a LangGraph StateGraph implementing the ReAct pattern.
    
    Args:
        tools: List of LangChain tool objects to bind to the LLM.
        llm: The LLM instance (ChatNVIDIA) to use for reasoning.
    
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
        thread_id = f"{state.get('platform')}:{state.get('sender_id')}"
        logger.info(f"[Node Trigger] 'agent' node entered for thread={thread_id}. Message count: {len(messages)}")
        
        response = await llm_with_tools.ainvoke(messages)
        
        # Log LLM decision
        if hasattr(response, "tool_calls") and response.tool_calls:
            calls = [f"{tc['name']}(args={tc['args']})" for tc in response.tool_calls]
            logger.info(f"[Node Event] 'agent' node calling tools: {', '.join(calls)}")
        else:
            snippet = response.content[:100] + "..." if len(response.content) > 100 else response.content
            logger.info(f"[Node Event] 'agent' node replying textually. Response snippet: {snippet!r}")
            
        return {"messages": [response]}
    
    # Create the tool execution node using LangGraph's prebuilt ToolNode
    tool_node_prebuilt = ToolNode(tools)
    
    async def logging_tool_node(state: AgentState) -> dict:
        """
        The tool node wrapper to log specific tool triggers and execution results.
        """
        messages = state["messages"]
        last_msg = messages[-1]
        
        tool_calls = getattr(last_msg, "tool_calls", [])
        calls_str = ", ".join([f"{tc['name']}(args={tc['args']})" for tc in tool_calls])
        logger.info(f"[Node Trigger] 'tools' node entered. Executing: {calls_str}")
        
        try:
            result = await tool_node_prebuilt.ainvoke(state)
            
            # Log results of tool executions
            if isinstance(result, dict) and "messages" in result:
                for msg in result["messages"]:
                    if hasattr(msg, "tool_call_id"):
                        tool_name = getattr(msg, "name", "unknown")
                        content_str = str(msg.content)
                        snippet = content_str[:200] + "..." if len(content_str) > 200 else content_str
                        logger.info(f"[Node Event] Tool '{tool_name}' (id={msg.tool_call_id}) completed. Result snippet: {snippet!r}")
            return result
        except Exception as e:
            logger.error(f"[Node Event] 'tools' node execution failed: {e}", exc_info=True)
            raise e
            
    # Build the graph
    graph = StateGraph(AgentState)
    
    # Add nodes
    graph.add_node("agent", agent_node)
    graph.add_node("tools", logging_tool_node)
    
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
    compiled = graph.compile()
    logger.debug("ReAct agent graph compiled successfully.")
    return compiled
