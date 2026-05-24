import os
import logging
from langchain_groq import ChatGroq
from ..state import CustomerState
from ..tools.handoff_tool import request_human_handoff
from shared.config import GROQ_API_KEY

logger = logging.getLogger("chatai_service.agents.support_agent")

async def support_agent_node(state: CustomerState) -> dict:
    """
    General support assistant agent node. Handles greetings, FAQs, and human handoff routing.
    """
    messages = list(state.get("messages", []))
    bot_name = state.get("bot_name", "Sahayak AI")
    retrieved_context = state.get("retrieved_context", [])
    
    base_instructions = (
        f"You are a helpful customer support assistant for {bot_name}.\n"
        "Your goal is to handle greetings, answer general questions, and assist the customer.\n"
        "If the customer specifically demands to speak to a human/agent, or if they seem frustrated with the AI, "
        "or if you do not know the answer to their question, you must call the `request_human_handoff` tool immediately.\n"
        "Be friendly, polite, and concise."
    )
    
    if retrieved_context:
        context_str = "\n".join(f"- {ctx}" for ctx in retrieved_context)
        base_instructions += f"\n\nHere is relevant context from past chats with this customer:\n{context_str}"

    
    if not GROQ_API_KEY:
        logger.error("GROQ_API_KEY missing.")
        from langchain_core.messages import AIMessage
        return {"messages": [AIMessage(content="Hello! How can we help you today?")]}
        
    try:
        llm = ChatGroq(
            groq_api_key=GROQ_API_KEY,
            model="llama-3.3-70b-versatile",
            temperature=0.5
        )
        
        tools = [request_human_handoff]
        llm_with_tools = llm.bind_tools(tools)
        
        system_message = {"role": "system", "content": base_instructions}
        
        chat_history = [system_message] + [
            {"role": m.type if hasattr(m, 'type') else m.get('role', 'user'), "content": m.content}
            for m in messages
        ]
        
        response = await llm_with_tools.ainvoke(chat_history)
        return {"messages": [response]}
    except Exception as e:
        logger.error(f"Error invoking Groq support agent: {e}")
        from langchain_core.messages import AIMessage
        return {"messages": [AIMessage(content="Hello! I'm here to help. What's on your mind?")]}
