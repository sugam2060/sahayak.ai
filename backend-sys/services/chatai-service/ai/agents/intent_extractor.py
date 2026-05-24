import os
import logging
from pydantic import BaseModel, Field
from langchain_groq import ChatGroq
from shared.database.schema.chat_message_mongo import MessageIntent
from ..state import CustomerState
from shared.config import GROQ_API_KEY

logger = logging.getLogger("chatai_service.agents.intent_extractor")

class IntentExtraction(BaseModel):
    intent: MessageIntent = Field(..., description="Identify if the customer has intent to buy a product (BUY) or not (NO_INTENT)")
    customer_info: dict = Field(default_factory=dict, description="Dictionary containing customer details extracted: 'name', 'phone', 'email', 'product_interest' if found. Keep empty if not found.")

async def extract_intent_node(state: CustomerState) -> dict:
    """
    Extracts the user message's purchase intent and any customer lead details.
    Runs in parallel to context retrieval.
    """
    messages = state.get("messages", [])
    if not messages:
        return {"intent": MessageIntent.NO_INTENT, "customer_info": {}}
        
    last_user_message = messages[-1].content
    
    
    if not GROQ_API_KEY:
        logger.warning("GROQ_API_KEY not found. Defaulting to NO_INTENT.")
        return {"intent": MessageIntent.NO_INTENT, "customer_info": {}}
        
    try:
        llm = ChatGroq(
            groq_api_key=GROQ_API_KEY,
            model="llama-3.3-70b-versatile",
            temperature=0
        )
        
        structured_llm = llm.with_structured_output(IntentExtraction)
        
        system_msg = (
            "You are an expert intent classifier. Analyze the last customer message and classify whether "
            "they have an interest in purchasing/ordering/pricing a product (BUY) or not (NO_INTENT).\n"
            "Also, extract any customer contact information (name, phone, email) or specific product_interest mentioned."
        )
        
        prompt = f"Customer message: {last_user_message}"
        
        result = await structured_llm.ainvoke([
            {"role": "system", "content": system_msg},
            {"role": "user", "content": prompt}
        ])
        
        logger.info(f"Intent extracted: {result.intent}, Customer Info: {result.customer_info}")
        return {
            "intent": result.intent,
            "customer_info": result.customer_info
        }
    except Exception as e:
        logger.error(f"Error in intent extractor: {e}")
        # Local keyword extraction fallback
        local_intent = MessageIntent.NO_INTENT
        if last_user_message:
            keywords = ["buy", "price", "order", "cost", "purchase", "how much", "shop", "pay"]
            if any(kw in last_user_message.lower() for kw in keywords):
                local_intent = MessageIntent.BUY
        return {"intent": local_intent, "customer_info": {}}
