from langchain_core.tools import tool

@tool
def request_human_handoff(reason: str) -> str:
    """
    Call this tool to hand off the conversation to a human representative.
    Use this if the customer explicitly demands to talk to a human agent, or
    if you detect that they are unhappy/discontent with the AI, or if you cannot answer their questions.
    """
    return f"HANDOFF_REQUESTED: {reason}"
