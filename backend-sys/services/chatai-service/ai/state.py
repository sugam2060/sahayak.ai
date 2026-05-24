from typing import Annotated, Sequence, TypedDict, Dict, Any, List
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages
from shared.database.schema.chat_message_mongo import MessageIntent

class CustomerState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], add_messages]
    intent: MessageIntent
    customer_info: Dict[str, Any]          # e.g., name, contact_info, interest
    organization_id: str
    bot_name: str
    chat_id: int
    sender_id: int
    retrieved_context: List[str]            # Past archived messages semantically retrieved via RAG
    catalog_context: List[str]              # SQL Database product catalog search matches
    handoff_requested: bool
