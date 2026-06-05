"""
AI Agent tools registry.
Collects and exports all tools for the LangGraph agent.
"""
from .orders.place_order import place_order
from .orders.get_order import get_order_details
from .orders.list_orders import list_customer_orders
from .orders.update_order import update_order_status
from .orders.cancel_order import cancel_order

from .products.search_products import search_products
from .products.get_product_detail import get_product_detail
from .products.check_stock import check_stock

from .ticket.create_ticket import create_support_ticket
from .ticket.get_ticket import get_ticket_detail
from .ticket.list_tickets import list_tickets
from .ticket.update_ticket import update_ticket

from .rag.rag_tool import search_knowledge_base

from .handoff.handoff_to_human import handoff_to_human
from .handoff.check_agent_availability import check_agent_availability

from .payment.send_payment_link import send_payment_link
from .payment.get_payment_status import get_payment_status
from .payment.initiate_refund import initiate_refund
from .payment.get_refund_status import get_refund_status


import functools
import logging

_tools_logger = logging.getLogger("chatai_service.ai.tools")


def _wrap_tool(tool_obj):
    """Wrap a single tool's invoke/ainvoke with diagnostic logging.
    
    Separate function to avoid the Python closure-over-loop-variable bug.
    """
    tool_name = tool_obj.name
    tool_log = logging.getLogger(f"chatai_service.ai.tools.{tool_name}")

    orig_ainvoke = tool_obj.ainvoke

    @functools.wraps(orig_ainvoke)
    async def wrapped_ainvoke(input, config=None, **kwargs):
        tool_log.info(f"[Tool] {tool_name} called")
        try:
            res = await orig_ainvoke(input, config=config, **kwargs)
            return res
        except Exception as e:
            tool_log.error(f"[Tool] {tool_name} failed: {e}", exc_info=True)
            raise

    object.__setattr__(tool_obj, 'ainvoke', wrapped_ainvoke)

    orig_invoke = tool_obj.invoke

    @functools.wraps(orig_invoke)
    def wrapped_invoke(input, config=None, **kwargs):
        tool_log.info(f"[Tool] {tool_name} called")
        try:
            res = orig_invoke(input, config=config, **kwargs)
            return res
        except Exception as e:
            tool_log.error(f"[Tool] {tool_name} failed: {e}", exc_info=True)
            raise

    object.__setattr__(tool_obj, 'invoke', wrapped_invoke)
    return tool_obj


def get_all_tools() -> list:
    """Returns the complete list of tools available to the AI agent."""
    raw_tools = [
        # Orders
        place_order,
        get_order_details,
        list_customer_orders,
        update_order_status,
        cancel_order,
        # Products
        search_products,
        get_product_detail,
        check_stock,
        # Tickets
        create_support_ticket,
        get_ticket_detail,
        list_tickets,
        update_ticket,
        # RAG
        search_knowledge_base,
        # Handoff
        handoff_to_human,
        check_agent_availability,
        # Payment (stubs)
        send_payment_link,
        get_payment_status,
        initiate_refund,
        get_refund_status,
    ]

    return [_wrap_tool(t) for t in raw_tools]
