"""
LLM provider configuration for the AI agent.
Uses Groq with llama-3.3-70b-versatile for fast inference with tool-calling support.
"""
import logging
from langchain_nvidia_ai_endpoints import ChatNVIDIA
from shared.config import NVIDIA_API_KEY

logger = logging.getLogger("chatai_service.ai.llm")

# Default model for agent reasoning (supports tool calling)
DEFAULT_MODEL = "meta/llama-3.3-70b-instruct"

# Lighter model for summarization tasks (faster, cheaper)
SUMMARY_MODEL = "meta/llama-3.1-8b-instruct"


def get_llm(model: str = DEFAULT_MODEL, temperature: float = 0.5) -> ChatNVIDIA:
    """
    Returns a NVIDIA AI LLM instance configured for the AI agent.
    
    Args:
        model: The NVIDIA AI model identifier.
        temperature: Sampling temperature (0 = deterministic).
    
    Returns:
        A ChatNVIDIA instance ready to bind tools.
    """
    if not NVIDIA_API_KEY:
        raise ValueError("NVIDIA_API_KEY is not configured. Set it in .env to enable AI agent.")
    
    kwargs = {
        "model": model,
        "api_key": NVIDIA_API_KEY,
        "temperature": temperature,
    }
    
    # Only add reasoning parameters if using deepseek-r1 or models that support reasoning
    if "deepseek-r1" in model:
        kwargs["max_tokens"] = 16384
        kwargs["reasoning_budget"] = 16384
        kwargs["chat_template_kwargs"] = {"enable_thinking": True}
        
    return ChatNVIDIA(**kwargs)


def get_summary_llm() -> ChatNVIDIA:
    """
    Returns a lighter LLM instance for conversation summarization.
    Uses a smaller model for speed and cost efficiency.
    """
    return get_llm(model=SUMMARY_MODEL, temperature=0.5)
