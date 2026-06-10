import logging
from typing import Union
from .manager import ChatServiceManager
from .handlers import ChatRouter

logger = logging.getLogger("chatai_service.chat_service")

# Initialize orchestrator manager
_manager = ChatServiceManager()

async def route_inbound_message(
    org_id: str,
    bot_name: str,
    bot_token: str,
    platform: str,
    payload: dict,
    event_type: str = "dm",
    **extra_fields
):
    """
    Produce the message event from any platform Webhook and send it to the kafka chat_service topic.
    Delegates to generic ChatRouter.
    """
    await ChatRouter.route_inbound(
        org_id=org_id,
        bot_name=bot_name,
        bot_token=bot_token,
        platform=platform,
        payload=payload,
        event_type=event_type,
        **extra_fields
    )

import re

def remove_markdown(text: str) -> str:
    """Strip markdown formatting (headers, bold, italics, code blocks, links) for plain-text platforms."""
    if not text:
        return text
    # Remove headers
    text = re.sub(r'^#+\s+', '', text, flags=re.MULTILINE)
    # Remove bold/italic (stars and underscores)
    text = re.sub(r'\*+\s*(.*?)\s*\*+', r'\1', text)
    text = re.sub(r'_+\s*(.*?)\s*_+', r'\1', text)
    # Remove code blocks
    text = re.sub(r'```[\s\S]*?```', '', text)
    # Remove inline code
    text = re.sub(r'`(.*?)`', r'\1', text)
    # Remove links [text](url) -> text
    text = re.sub(r'\[(.*?)\]\(.*?\)', r'\1', text)
    return text.strip()

async def route_outbound_reply(
    org_id: str,
    bot_name: str,
    bot_token: str,
    platform: str,
    chat_id: Union[int, str],
    sender_id: Union[int, str],
    text: str,
    image_url: str = None,
    ig_account_id: str = None
):
    """
    Produce the outbound reply message event and send it to the kafka chat_service topic.
    Delegates to generic ChatRouter.
    """
    await ChatRouter.route_outbound(
        org_id=org_id,
        bot_name=bot_name,
        bot_token=bot_token,
        platform=platform,
        chat_id=chat_id,
        sender_id=sender_id,
        text=text,
        image_url=image_url,
        ig_account_id=ig_account_id
    )

async def handle_chat_event(event: dict):
    """
    Handles both inbound and outbound chat events consumed from Kafka by delegating to the manager.
    """
    try:
        await _manager.handle_event(event)
    except Exception as e:
        logger.error(f"Error handling event in manager: {e}", exc_info=True)
        raise e
