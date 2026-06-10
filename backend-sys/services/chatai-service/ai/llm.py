"""
LLM provider configuration for the AI agent.
Provides a unified LLMProvider class for retrieving structured/unstructured ChatNVIDIA instances.
"""
import logging
from typing import Optional, Any
from langchain_nvidia_ai_endpoints import ChatNVIDIA
from pydantic import BaseModel, Field
from shared.config import NVIDIA_API_KEY

logger = logging.getLogger("chatai_service.ai.llm")

# Default model definitions (for backward compatibility references)
DEFAULT_MODEL = "nvidia/nemotron-3-super-120b-a12b"
SUMMARY_MODEL = "meta/llama-3.1-8b-instruct"


class SearchKeywords(BaseModel):
    keywords: list[str] = Field(
        ...,
        description="A list of synonym keywords or related terms for the product search query."
    )


class LLMProvider:
    # Registry of all models, names, default temperatures, and roles
    MODEL_DESCRIPTIONS = {
        "reasoning": {
            "model_name": "nvidia/nemotron-3-super-120b-a12b",
            "temperature": 0.5,
            "description": "Default reasoning and agent planning model. Supports tool calling.",
        },
        "lightweight": {
            "model_name": "meta/llama-3.1-8b-instruct",
            "temperature": 1.0,
            "description": "Lighter, faster, and cheaper model for query expansion and simple tasks.",
        },
        "deepseek_flash": {
            "model_name": "deepseek-ai/deepseek-v4-flash",
            "temperature": 1.0,
            "description": "Fast deepseek flash model without thinking/reasoning enabled.",
        },
        "deepseek_pro": {
            "model_name": "deepseek-ai/deepseek-v4-pro",
            "temperature": 1.0,
            "description": "Deepseek pro model with thinking/reasoning enabled.",
        }
    }

    @staticmethod
    def _create_instance(
        model_key: str,
        structured: bool = False,
        response_model: Optional[type[BaseModel]] = None,
        temperature: Optional[float] = None
    ) -> Any:
        if model_key not in LLMProvider.MODEL_DESCRIPTIONS:
            raise ValueError(f"Unknown model key: {model_key}")
        
        cfg = LLMProvider.MODEL_DESCRIPTIONS[model_key]
        model_name = cfg["model_name"]
        default_temp = cfg["temperature"]
        temp = temperature if temperature is not None else default_temp
        
        if not NVIDIA_API_KEY:
            raise ValueError("NVIDIA_API_KEY is not configured. Set it in .env to enable AI agent.")
            
        kwargs = {
            "model": model_name,
            "api_key": NVIDIA_API_KEY,
            "temperature": temp,
        }
        
        # Apply specific model configurations
        if "deepseek-ai/deepseek-v4-flash" in model_name:
            kwargs["temperature"] = temp
            kwargs["top_p"] = 0.95
            kwargs["max_tokens"] = 16384
            kwargs["extra_body"] = {"chat_template_kwargs": {"thinking": False}}
        elif "deepseek-ai/deepseek-v4-pro" in model_name:
            kwargs["temperature"] = temp
            kwargs["top_p"] = 0.95
            kwargs["max_tokens"] = 16384
            kwargs["extra_body"] = {"chat_template_kwargs": {"thinking": True, "reasoning_effort": "high"}}
        elif "nemotron-3-super-120b" in model_name:
            kwargs["top_p"] = 0.95
            kwargs["max_completion_tokens"] = 16384
            kwargs["model_kwargs"] = {
                "reasoning_budget": 16384,
                "chat_template_kwargs": {"enable_thinking": True}
            }
            
        llm = ChatNVIDIA(**kwargs)
        if structured and response_model is not None:
            return llm.with_structured_output(response_model)
        return llm

    @staticmethod
    def get_reasoning_model(
        structured: bool = False,
        response_model: Optional[type[BaseModel]] = None,
        temperature: Optional[float] = None
    ) -> Any:
        """Returns the default reasoning model (nvidia/nemotron-3-super-120b-a12b)."""
        return LLMProvider._create_instance("reasoning", structured, response_model, temperature)

    @staticmethod
    def get_lightweight_model(
        structured: bool = False,
        response_model: Optional[type[BaseModel]] = None,
        temperature: Optional[float] = None
    ) -> Any:
        """Returns the lightweight model (meta/llama-3.1-8b-instruct)."""
        return LLMProvider._create_instance("lightweight", structured, response_model, temperature)

    @staticmethod
    def get_deepseek_flash(
        structured: bool = False,
        response_model: Optional[type[BaseModel]] = None,
        temperature: Optional[float] = None
    ) -> Any:
        """Returns the deepseek v4 flash model without thinking."""
        return LLMProvider._create_instance("deepseek_flash", structured, response_model, temperature)

    @staticmethod
    def get_deepseek_pro(
        structured: bool = False,
        response_model: Optional[type[BaseModel]] = None,
        temperature: Optional[float] = None
    ) -> Any:
        """Returns the deepseek v4 pro model with thinking/reasoning."""
        return LLMProvider._create_instance("deepseek_pro", structured, response_model, temperature)


# Legacy functional API for backward compatibility
def get_llm(model: str = DEFAULT_MODEL, temperature: float = 0.5) -> ChatNVIDIA:
    """Legacy wrapper for retrieving ChatNVIDIA instances by model string identifier."""
    if model == "nvidia/nemotron-3-super-120b-a12b":
        return LLMProvider.get_reasoning_model(temperature=temperature)
    elif model == "meta/llama-3.1-8b-instruct":
        return LLMProvider.get_lightweight_model(temperature=temperature)
    elif model == "deepseek-ai/deepseek-v4-flash":
        return LLMProvider.get_deepseek_flash(temperature=temperature)
    elif model == "deepseek-ai/deepseek-v4-pro":
        return LLMProvider.get_deepseek_pro(temperature=temperature)
    else:
        return ChatNVIDIA(model=model, api_key=NVIDIA_API_KEY, temperature=temperature)


def get_summary_llm() -> ChatNVIDIA:
    """Legacy wrapper for retrieving the lightweight summary LLM instance."""
    return LLMProvider.get_lightweight_model()
