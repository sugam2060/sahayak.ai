import os
import logging
from langchain_groq import ChatGroq
from shared.database.mongodb import MongoDBManager
from .embeddings import save_message_embedding

logger = logging.getLogger("chatai_service.memory")

async def summarize_history(previous_summary: str, messages_to_summarize: list[dict]) -> str:
    """
    Summarize the given messages combined with the previous summary using Groq.
    """
    groq_api_key = os.getenv("GROQ_API_KEY")
    if not groq_api_key:
        logger.warning("GROQ_API_KEY not found in environment. Skipping summarization.")
        return previous_summary or "Conversation started."
        
    try:
        msg_lines = []
        for m in messages_to_summarize:
            direction = m.get("direction", "inbound")
            sender = m.get("sender_name", "User")
            text = m.get("text", "")
            msg_lines.append(f"{sender} ({direction}): {text}")
            
        new_history_text = "\n".join(msg_lines)
        
        prompt = (
            "You are a helpful AI assistant summarizing a customer conversation history.\n"
            f"Existing Summary: {previous_summary or 'No previous summary.'}\n\n"
            f"New message exchanges to add and summarize:\n{new_history_text}\n\n"
            "Please output a concise, updated summary of the conversation to help downstream agents "
            "understand the customer's queries, context, and current status. Be concise and factual."
        )
        
        llm = ChatGroq(
            groq_api_key=groq_api_key,
            model="llama-3.3-70b-versatile",
            temperature=0.0
        )
        
        resp = await llm.ainvoke(prompt)
        summary = str(resp.content).strip()
        logger.info("Successfully generated updated conversation summary via Groq.")
        return summary
    except Exception as e:
        logger.error(f"Failed to generate conversation summary: {e}")
        return previous_summary or "Conversation started."

async def compress_conversation_history(sender_id: int, platform: str):
    """
    Manage the context window using the 8:6 compression ratio.
    If the active message count reaches 8:
    1. Summarize the previous summary + the oldest 6 messages.
    2. Archive the 6 messages in the RAG vector database.
    3. Update the MongoDB conversation to keep only the last 2 messages and store the new summary.
    """
    db = MongoDBManager.get_db()
    conv = await db.conversations.find_one({
        "platform": platform.lower(),
        "user.sender_id": sender_id
    })
    if not conv:
        return
        
    messages = conv.get("messages", [])
    if len(messages) < 8:
        return
        
    logger.info(f"Triggering 8:6 memory compression for sender: {sender_id} ({platform})")
    
    num_to_delete = len(messages) - 2
    to_summarize = messages[:num_to_delete]
    to_retain = messages[num_to_delete:]
    
    prev_summary = conv.get("previous_summary")
    
    new_summary = await summarize_history(prev_summary, to_summarize)
    
    for m in to_summarize:
        text = m.get("text", "")
        if text.strip():
            await save_message_embedding(sender_id, platform, text)
            
    await db.conversations.update_one(
        {
            "platform": platform.lower(),
            "user.sender_id": sender_id
        },
        {
            "$set": {
                "previous_summary": new_summary,
                "messages": to_retain
            }
        }
    )
    logger.info(f"Memory compression complete: {num_to_delete} messages archived, 2 retained, summary updated.")
