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
        return "tools"
    
    # Otherwise, we're done — the agent has produced a final response
    return END


def build_agent_graph(tools: list, llm):
    """
    Build and compile a LangGraph StateGraph implementing the ReAct pattern.
    
    Args:
        tools: List of LangChain tool objects to bind to the LLM.
        llm: The LLM instance (ChatGroq) to use for reasoning.
    
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
        response = await llm_with_tools.ainvoke(messages)
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
    compiled = graph.compile()
    logger.debug("ReAct agent graph compiled successfully.")
    return compiled
