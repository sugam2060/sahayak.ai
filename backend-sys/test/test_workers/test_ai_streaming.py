import pytest
import asyncio
import importlib
from unittest.mock import AsyncMock, patch, MagicMock

# Dynamically import modules with hyphens
event_emitter_module = importlib.import_module("services.chatai-service.ai.event_emitter")
AIEventEmitter = event_emitter_module.AIEventEmitter

agent_module = importlib.import_module("services.chatai-service.ai.agent")
run_agent = agent_module.run_agent

@pytest.mark.asyncio
async def test_ai_event_emitter():
    with patch("shared.kafka_producer.KafkaProducerPool.send_message", new_callable=AsyncMock) as mock_send:
        await AIEventEmitter.emit(
            org_id="org-123",
            platform="telegram",
            sender_id="sender-456",
            event="thinking",
            status="started"
        )
        mock_send.assert_called_once_with(
            "chat_websocket",
            {
                "type": "ai_event",
                "org_id": "org-123",
                "platform": "telegram",
                "sender_id": "sender-456",
                "event": "thinking",
                "status": "started"
            }
        )

@pytest.mark.asyncio
async def test_run_agent_streaming_abort():
    # Mock MongoDB
    mock_db = MagicMock()
    mock_db.conversations = AsyncMock()
    
    # We want find_one to return ai_assigned=True initially, then False (to simulate abort)
    call_count = 0
    async def mock_find_one(query, projection=None):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            # First load
            return {
                "organization_id": "org-123",
                "platform": "telegram",
                "user": {"sender_id": "sender-456"},
                "ai_assigned": True,
                "messages": []
            }
        else:
            # Subsequent checks during streaming
            return {"ai_assigned": False}

    mock_db.conversations.find_one = mock_find_one

    # Mock MongoDB Saver checkpointer to not require real MongoClient
    mock_saver = MagicMock()
    mock_saver.aget_state = AsyncMock(return_value=MagicMock(values={}))
    mock_saver.get_state = AsyncMock(return_value=MagicMock(values={}))

    # Mock Graph
    # Let's create a mock stream that yields some nodes
    async def mock_astream(*args, **kwargs):
        yield {"chat": {"messages": []}}
        yield {"tools": {"messages": []}}

    mock_graph = MagicMock()
    mock_graph.astream = mock_astream
    mock_graph.aget_state = AsyncMock(return_value=MagicMock(values={}))

    # Mock LLM and AI config fetcher
    mock_llm_provider = MagicMock()
    mock_llm_provider.get_reasoning_model = MagicMock()

    with patch.object(agent_module, "_fetch_ai_config", new_callable=AsyncMock) as mock_config, \
         patch.object(agent_module, "LLMProvider", mock_llm_provider), \
         patch.object(agent_module, "get_all_tools", return_value=[]), \
         patch("langgraph.checkpoint.mongodb.MongoDBSaver", return_value=mock_saver), \
         patch("pymongo.MongoClient"), \
         patch.object(agent_module, "build_agent_graph", return_value=mock_graph), \
         patch("shared.database.mongodb.MongoDBManager.get_db", return_value=mock_db), \
         patch("shared.kafka_producer.KafkaProducerPool.send_message", new_callable=AsyncMock) as mock_send_ws:

        mock_config.return_value = {
            "ai_enabled": True,
            "auto_order_enabled": False,
            "system_prompt": "Prompt",
            "knowledge_base": ""
        }

        # Run agent
        result = await run_agent(
            org_id="de851b5f-b375-4942-862a-3a9406a2f1da",
            platform="telegram",
            sender_id="9999",
            chat_id="8888",
            bot_name="TestBot",
            bot_token="mock-token",
            inbound_text="hello",
        )

        # Assert agent was aborted and returned None
        assert result is None

        # Verify event websocket messages sent include 'aborted'
        emitted_events = [call[0][1]["event"] for call in mock_send_ws.call_args_list]
        assert "processing" in emitted_events
        assert "aborted" in emitted_events
