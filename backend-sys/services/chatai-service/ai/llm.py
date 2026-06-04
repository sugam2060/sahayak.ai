"""
LLM provider configuration for the AI agent.
Uses Groq with llama-3.3-70b-versatile for fast inference with tool-calling support.
"""
import logging
from langchain_groq import ChatGroq
from shared.config import GROQ_API_KEY

logger = logging.getLogger("chatai_service.ai.llm")

# Default model for agent reasoning (supports tool calling)
DEFAULT_MODEL = "llama-3.3-70b-versatile"

# Lighter model for summarization tasks (faster, cheaper)
SUMMARY_MODEL = "llama-3.1-8b-instant"


def get_llm(model: str = DEFAULT_MODEL, temperature: float = 0) -> ChatGroq:
    """
    Returns a ChatGroq LLM instance configured for the AI agent.
    
    Args:
        model: The Groq model identifier.
        temperature: Sampling temperature (0 = deterministic).
    
    Returns:
        A ChatGroq instance ready to bind tools.
    """
    if not GROQ_API_KEY:
        raise ValueError("GROQ_API_KEY is not configured. Set it in .env to enable AI agent.")
    
    return ChatGroq(
        api_key=GROQ_API_KEY,
        model=model,
        temperature=temperature,
        max_retries=2,
    )


def get_summary_llm() -> ChatGroq:
    """
    Returns a lighter LLM instance for conversation summarization.
    Uses a smaller model for speed and cost efficiency.
    """
    return get_llm(model=SUMMARY_MODEL, temperature=0)


llm = get_llm()

result = llm.invoke("Hello world")

print(result)
