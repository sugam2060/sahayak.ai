import pytest
import importlib

memory_module = importlib.import_module("services.chatai-service.ai.memory")
build_system_message = memory_module.build_system_message
extract_bot_name = memory_module.extract_bot_name

def test_extract_bot_name():
    assert extract_bot_name("your name is: 'Alice'", "Default") == "Alice"
    assert extract_bot_name("respond as: Bob", "Default") == "Bob"
    assert extract_bot_name("name is 'Charlie'", "Default") == "Charlie"
    assert extract_bot_name("normal instructions here", "Default") == "Default"

def test_build_system_message_no_customer_details():
    msg = build_system_message(
        system_prompt="Custom instructions",
        previous_summary="Summary of convo",
        platform="instagram",
        bot_name="MyBot",
        auto_order_enabled=True
    )
    content = msg.content
    assert "Custom instructions" in content
    assert "Summary of convo" in content
    assert "MyBot" in content
    assert "No phone number or delivery address is currently on file" in content

def test_build_system_message_with_customer_details():
    msg = build_system_message(
        system_prompt="Custom instructions",
        previous_summary=None,
        platform="instagram",
        bot_name="MyBot",
        auto_order_enabled=True,
        customer_phone="+9779841234567",
        customer_address="Kathmandu, Nepal"
    )
    content = msg.content
    assert "Custom instructions" in content
    assert "MyBot" in content
    assert "Phone Number: +9779841234567" in content
    assert "Delivery Address: Kathmandu, Nepal" in content
    assert "You have the following customer details on file. Use them directly" in content
    assert "STRICT ORDERING: You MUST retrieve the actual product_id" in content

def test_split_message():
    instagram_module = importlib.import_module("services.chatai-service.handlers.instagram_handler")
    split_message = instagram_module.split_message
    
    # Simple message under limit
    assert split_message("hello world", limit=20) == ["hello world"]
    
    # Message splitting on space
    text = "hello beautiful world out there"
    chunks = split_message(text, limit=17)
    assert chunks == ["hello beautiful", "world out there"]
    
    # Message splitting on newline
    text_nl = "first line\nsecond line here"
    chunks_nl = split_message(text_nl, limit=12)
    assert chunks_nl == ["first line", "second line", "here"]
    
    # Force split when no spaces exist
    text_force = "extremelylongwordwithoutanyspaces"
    chunks_force = split_message(text_force, limit=10)
    assert chunks_force == ["extremelyl", "ongwordwit", "houtanyspa", "ces"]
    
    # Empty string
    assert split_message("", limit=10) == []

