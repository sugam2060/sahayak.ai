import os
import logging
from uuid import UUID
from sqlalchemy.future import select
from langchain_groq import ChatGroq
from shared.database.engine import SessionLocal
from shared.database.schema.organization_config_ai import OrganizationConfigAI
from ..state import CustomerState
from ..tools.db_tools import lookup_products, check_product_availability
from shared.config import GROQ_API_KEY

logger = logging.getLogger("chatai_service.agents.sales_agent")

async def fetch_organization_system_prompt(organization_id: str) -> str:
    try:
        org_uuid = UUID(organization_id)
    except ValueError:
        return ""
    try:
        async with SessionLocal() as session:
            stmt = select(OrganizationConfigAI).where(OrganizationConfigAI.organization_id == org_uuid)
            result = await session.execute(stmt)
            config = result.scalars().first()
            if config and config.system_prompt:
                return config.system_prompt
    except Exception as e:
        logger.error(f"Error fetching organization system prompt from PostgreSQL: {e}")
    return ""

async def sales_agent_node(state: CustomerState) -> dict:
    """
    Sales agent conversational node. Uses custom system prompt, RAG context, and product tools.
    """
    messages = list(state.get("messages", []))
    org_id = state.get("organization_id", "")
    bot_name = state.get("bot_name", "Sahayak AI")
    retrieved_context = state.get("retrieved_context", [])
    customer_info = state.get("customer_info", {})
    
    db_system_prompt = await fetch_organization_system_prompt(org_id)
    
    base_instructions = (
        f"You are a professional sales representative bot named {bot_name}.\n"
        "Your goal is to assist customers with product inquiries, pricing, availability, and guide them through buying decisions.\n"
        "Use the tools available to search products or check stock levels. Always check availability before confirming an order.\n"
        "Be polite, helpful, and concise."
    )
    
    if db_system_prompt:
        base_instructions += f"\n\nSpecific Organization Instructions:\n{db_system_prompt}"
        
    if retrieved_context:
        context_str = "\n".join(f"- {ctx}" for ctx in retrieved_context)
        base_instructions += f"\n\nHere is relevant context from past chats with this customer:\n{context_str}"
        
    if customer_info:
        info_str = ", ".join(f"{k}: {v}" for k, v in customer_info.items() if v)
        if info_str:
            base_instructions += f"\n\nExtracted Customer Information:\n{info_str}"
            
    base_instructions += f"\n\nIMPORTANT context for tools: Use organization_id='{org_id}' when executing lookup_products or check_product_availability."

    
    if not GROQ_API_KEY:
        logger.error("GROQ_API_KEY missing.")
        from langchain_core.messages import AIMessage
        return {"messages": [AIMessage(content="Hello! How can we assist you with our products today?")]}
        
    try:
        llm = ChatGroq(
            groq_api_key=GROQ_API_KEY,
            model="llama-3.3-70b-versatile",
            temperature=0.4
        )
        
        tools = [lookup_products, check_product_availability]
        llm_with_tools = llm.bind_tools(tools)
        
        system_message = {"role": "system", "content": base_instructions}
        
        chat_history = [system_message] + [
            {"role": m.type if hasattr(m, 'type') else m.get('role', 'user'), "content": m.content}
            for m in messages
        ]
        
        response = await llm_with_tools.ainvoke(chat_history)
        return {"messages": [response]}
    except Exception as e:
        logger.error(f"Error invoking Groq sales agent: {e}")
        from langchain_core.messages import AIMessage
        return {"messages": [AIMessage(content="I'm having trouble retrieving details. How can I assist you today?")]}
