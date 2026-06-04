"""
Conversation memory management for the AI agent.

Implements the 10:5 rolling summary strategy:
- When conversation has >= 15 messages, summarize first 10 + previous_summary
- Keep last 5 messages as-is for immediate context
- Store the generated summary back to MongoDB's `previous_summary` field
"""
import logging
from datetime import datetime, timezone
from typing import Optional
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage

logger = logging.getLogger("chatai_service.ai.memory")

# Memory thresholds
SUMMARY_THRESHOLD = 15   # Trigger summarization when messages >= this
MESSAGES_TO_SUMMARIZE = 10  # Number of older messages to summarize
RECENT_MESSAGES_TO_KEEP = 5  # Number of recent messages to keep verbatim


def _mongo_msg_to_langchain(msg: dict):
    """Convert a MongoDB MessageDetail dict to a LangChain message."""
    text = msg.get("text", "")
    image_url = msg.get("image_url")
    
    # Include image info in message content if present
    content = text
    if image_url:
        content = f"{text}\n[Image: {image_url}]" if text else f"[Image: {image_url}]"
    
    direction = msg.get("direction", "inbound")
    if direction == "inbound":
        return HumanMessage(content=content)
    else:
        return AIMessage(content=content)


async def load_conversation_memory(
    db,
    platform: str,
    sender_id,
    max_recent: int = RECENT_MESSAGES_TO_KEEP
) -> tuple[list, Optional[str]]:
    """
    Load conversation history from MongoDB and convert to LangChain messages.
    
    Args:
        db: MongoDB database instance
        platform: Platform name (telegram, instagram, etc.)
        sender_id: The sender's platform-specific ID
        max_recent: Maximum number of recent messages to include verbatim
    
    Returns:
        Tuple of (list[BaseMessage], previous_summary: str | None)
    """
    # Handle int/str sender_id matching (same pattern as handlers)
    sender_id_int = int(sender_id) if str(sender_id).isdigit() else None
    query_id = {"$in": [sender_id, sender_id_int]} if sender_id_int is not None else sender_id
    
    conv = await db.conversations.find_one({
        "platform": platform,
        "user.sender_id": query_id
    })
    
    if not conv:
        return [], None
    
    messages = conv.get("messages", [])
    previous_summary = conv.get("previous_summary")
    
    if not messages:
        return [], previous_summary
    
    # Convert the most recent messages to LangChain format
    recent_messages = messages[-max_recent:] if len(messages) > max_recent else messages
    langchain_messages = [_mongo_msg_to_langchain(m) for m in recent_messages]
    
    return langchain_messages, previous_summary


async def maybe_summarize_and_compact(
    db,
    platform: str,
    sender_id,
    llm
) -> None:
    """
    Check if the conversation exceeds the threshold and perform summarization.
    
    Implements the 10:5 strategy:
    - If conversation has >= 15 messages:
      1. Take the first 10 messages
      2. Combine with any existing previous_summary
      3. Ask LLM to create a new summary
      4. Store summary in MongoDB's previous_summary field
      5. Remove the first 10 messages from the messages array
    
    Args:
        db: MongoDB database instance
        platform: Platform name
        sender_id: Sender's platform ID
        llm: LLM instance for generating summaries
    """
    sender_id_int = int(sender_id) if str(sender_id).isdigit() else None
    query_id = {"$in": [sender_id, sender_id_int]} if sender_id_int is not None else sender_id
    
    conv = await db.conversations.find_one({
        "platform": platform,
        "user.sender_id": query_id
    })
    
    if not conv:
        return
    
    messages = conv.get("messages", [])
    if len(messages) < SUMMARY_THRESHOLD:
        return
    
    actual_sender_id = conv["user"]["sender_id"]
    previous_summary = conv.get("previous_summary") or ""
    
    # Take the first MESSAGES_TO_SUMMARIZE messages for summarization
    messages_to_summarize = messages[:MESSAGES_TO_SUMMARIZE]
    remaining_messages = messages[MESSAGES_TO_SUMMARIZE:]
    
    # Build the summarization prompt
    conversation_text = _format_messages_for_summary(messages_to_summarize)
    
    summary_prompt = _build_summary_prompt(previous_summary, conversation_text)
    
    try:
        response = await llm.ainvoke([HumanMessage(content=summary_prompt)])
        new_summary = response.content.strip()
        
        # Re-index message_ids for remaining messages (1-based)
        for idx, msg in enumerate(remaining_messages, start=1):
            msg["message_id"] = idx
        
        # Update MongoDB: store new summary, keep only remaining messages
        await db.conversations.update_one(
            {
                "platform": platform,
                "user.sender_id": actual_sender_id
            },
            {
                "$set": {
                    "previous_summary": new_summary,
                    "messages": remaining_messages,
                    "updated_at": datetime.now(timezone.utc)
                }
            }
        )
        
        logger.info(
            f"Summarized {MESSAGES_TO_SUMMARIZE} messages for {platform}:{actual_sender_id}. "
            f"Remaining: {len(remaining_messages)} messages."
        )
    except Exception as e:
        logger.error(f"Failed to summarize conversation: {e}", exc_info=True)
        # Don't crash the agent if summarization fails — just skip


def _format_messages_for_summary(messages: list) -> str:
    """Format MongoDB messages into a readable text for summarization."""
    lines = []
    for msg in messages:
        direction = msg.get("direction", "inbound")
        sender = msg.get("sender_name", "Unknown")
        text = msg.get("text", "")
        role = "Customer" if direction == "inbound" else "Agent"
        if text:
            lines.append(f"{role} ({sender}): {text}")
    return "\n".join(lines)


def _build_summary_prompt(previous_summary: str, conversation_text: str) -> str:
    """Build the prompt for conversation summarization."""
    parts = [
        "Summarize the following conversation between a customer and a support agent. "
        "Capture key details: customer requests, issues, orders discussed, products mentioned, "
        "decisions made, and any unresolved items. Be concise but thorough."
    ]
    
    if previous_summary:
        parts.append(f"\n\nPrevious conversation summary:\n{previous_summary}")
    
    parts.append(f"\n\nNew conversation messages to summarize:\n{conversation_text}")
    parts.append("\n\nProvide a concise summary:")
    
    return "\n".join(parts)


def build_system_message(
    system_prompt: str,
    previous_summary: Optional[str],
    platform: str,
    bot_name: str,
    auto_order_enabled: bool
) -> SystemMessage:
    """
    Construct the system message for the AI agent, combining:
    - Organization's custom system prompt
    - Conversation summary (if any)
    - Platform context
    - Behavioral instructions
    
    Args:
        system_prompt: Custom system prompt from organization_config_ai
        previous_summary: Rolling summary of older conversation messages
        platform: Current platform (telegram, instagram, etc.)
        bot_name: Name of the bot
        auto_order_enabled: Whether auto-ordering is enabled
    
    Returns:
        A SystemMessage with full context for the agent.
    """
    parts = []
    
    # Organization's custom instructions
    if system_prompt:
        parts.append(f"## Your Instructions\n{system_prompt}")
    
    # Behavioral guidelines
    parts.append(
        "\n## Behavioral Guidelines\n"
        "- You are a helpful customer support assistant.\n"
        "- Think step-by-step before taking any action.\n"
        "- Always search the knowledge base first before saying you don't know something.\n"
        "- Be polite, professional, and concise in your responses.\n"
        "- If you cannot resolve the customer's issue, use the handoff_to_human tool.\n"
        f"- You are responding on the {platform} platform as '{bot_name}'.\n"
        "- Do NOT use markdown formatting (no **, ##, etc.) in your final text replies to the user — "
        "these platforms render plain text only. However, you must still output standard tool calls normally when calling tools.\n"
        "- Keep responses short and conversational, suitable for a chat interface."
    )
    
    # Order handling rules
    if auto_order_enabled:
        parts.append(
            "\n## Order Handling\n"
            "- Auto-ordering is ENABLED. You may place orders directly when the customer confirms.\n"
            "- Always confirm the items, quantities, and delivery details before placing an order.\n"
            "- After placing an order, share the order ID and tracking information."
        )
    else:
        parts.append(
            "\n## Order Handling\n"
            "- Auto-ordering is DISABLED. Do NOT place orders directly.\n"
            "- If a customer wants to order, collect their requirements and hand off to a human agent."
        )
    
    # Conversation summary context
    if previous_summary:
        parts.append(
            f"\n## Previous Conversation Context\n"
            f"Summary of earlier messages with this customer:\n{previous_summary}"
        )
    
    return SystemMessage(content="\n".join(parts))
