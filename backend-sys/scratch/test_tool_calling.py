import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from langchain_nvidia_ai_endpoints import ChatNVIDIA
from shared.config import NVIDIA_API_KEY
from langchain_core.tools import tool

@tool
def get_weather(location: str) -> str:
    """Get the weather for a given location."""
    return f"The weather in {location} is sunny."

def main():
    llm = ChatNVIDIA(model="meta/llama-3.3-70b-instruct", api_key=NVIDIA_API_KEY, temperature=0)
    llm_with_tools = llm.bind_tools([get_weather])
    print("Invoking...")
    res = llm_with_tools.invoke("What's the weather in Kathmandu?")
    print("Response:", res)

if __name__ == "__main__":
    main()
