import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock
import importlib

chat_worker_module = importlib.import_module("services.chatai-service.chat_worker")
KafkaChatWorker = chat_worker_module.KafkaChatWorker
chat_service_module = importlib.import_module("services.chatai-service.chat_service")

# Dynamically import the graph module so we can patch get_agent_graph
ai_graph = importlib.import_module("services.chatai-service.ai.graph")

@pytest.mark.asyncio
async def test_kafka_chat_worker_consume_inbound():
    # Mock MongoDBManager
    mock_db = MagicMock()
    mock_db.conversations = AsyncMock()
    
    # Mock AIOKafkaConsumer
    mock_consumer = MagicMock()
    mock_consumer.start = AsyncMock()
    mock_consumer.stop = AsyncMock()
    
    # Create a mock message pack returned by getmany
    mock_msg = MagicMock()
    mock_msg.value = {
        "org_id": "test-org-123",
        "bot_name": "TestBot",
        "bot_token": "mock-token",
        "platform": "telegram",
        "direction": "inbound",
        "payload": {
            "message": {
                "message_id": 100,
                "from": {
                    "id": 9999,
                    "first_name": "Alice",
                    "username": "alice"
                },
                "chat": {
                    "id": 8888
                },
                "text": "Hello bot"
            }
        }
    }
    
    class MockConsumerPack:
        def __init__(self, msg):
            self.msg = msg
            self.called = False
            
        async def getmany(self, timeout_ms=1000):
            if not self.called:
                self.called = True
                return {("chat_service", 0): [self.msg]}
            else:
                await asyncio.sleep(0.1)
                raise asyncio.CancelledError()
                
    mock_pack = MockConsumerPack(mock_msg)
    mock_consumer.getmany = mock_pack.getmany

    worker = KafkaChatWorker()
    
    # Mock graph & state snapshot
    mock_graph = MagicMock()
    mock_graph.aget_state = AsyncMock(return_value=None)
    mock_graph.aupdate_state = AsyncMock()
    
    with patch.object(chat_worker_module, "AIOKafkaConsumer", return_value=mock_consumer), \
         patch("shared.database.mongodb.MongoDBManager.get_db", return_value=mock_db), \
         patch.object(ai_graph, "get_agent_graph", return_value=mock_graph), \
         patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
         
        mock_db.conversations.find_one = AsyncMock(return_value=None)
        mock_db.conversations.update_one = AsyncMock()
        
        try:
            await worker.start()
        except asyncio.CancelledError:
            pass
            
        # Verify MongoDB conversations.update_one was called exactly once (for metadata insert)
        assert mock_db.conversations.update_one.call_count == 1
        
        # Check first call args (inbound)
        first_call_args = mock_db.conversations.update_one.call_args_list[0]
        query = first_call_args[0][0]
        update = first_call_args[0][1]
        assert query == {"thread_id": "telegram:9999"}
        assert update["$setOnInsert"]["organization_id"] == "test-org-123"
        assert update["$setOnInsert"]["bot_name"] == "TestBot"
        assert update["$setOnInsert"]["chat_id"] == 8888
        assert update["$set"]["user"]["sender_name"] == "Alice"
        
        # Verify the message update was correctly routed to the checkpointer state
        mock_graph.aupdate_state.assert_called_once()
        call_args = mock_graph.aupdate_state.call_args
        config_arg = call_args[0][0]
        state_update = call_args[0][1]
        assert config_arg == {"configurable": {"thread_id": "telegram:9999"}}
        messages = state_update["messages"]
        assert len(messages) == 1
        assert messages[0].content == "Hello bot"
        
        # Verify Telegram Bot API was NOT called for inbound messages
        mock_post.assert_not_called()

@pytest.mark.asyncio
async def test_kafka_chat_worker_consume_outbound():
    # Mock MongoDBManager
    mock_db = MagicMock()
    mock_db.conversations = AsyncMock()
    
    # Mock AIOKafkaConsumer
    mock_consumer = MagicMock()
    mock_consumer.start = AsyncMock()
    mock_consumer.stop = AsyncMock()
    
    # Create a mock message pack returned by getmany
    mock_msg = MagicMock()
    mock_msg.value = {
        "org_id": "test-org-123",
        "bot_name": "TestBot",
        "bot_token": "mock-token",
        "platform": "telegram",
        "direction": "outbound",
        "chat_id": 8888,
        "sender_id": 9999,
        "text": "Hello outbound reply"
    }
    
    class MockConsumerPack:
        def __init__(self, msg):
            self.msg = msg
            self.called = False
            
        async def getmany(self, timeout_ms=1000):
            if not self.called:
                self.called = True
                return {("chat_service", 0): [self.msg]}
            else:
                await asyncio.sleep(0.1)
                raise asyncio.CancelledError()
                
    mock_pack = MockConsumerPack(mock_msg)
    mock_consumer.getmany = mock_pack.getmany

    worker = KafkaChatWorker()
    
    # Mock graph & state snapshot
    mock_graph = MagicMock()
    
    # Mock the state snapshot containing no previous messages (so duplicate check passes)
    class MockStateSnapshot:
        def __init__(self):
            self.values = {"messages": []}
            
    mock_graph.aget_state = AsyncMock(return_value=MockStateSnapshot())
    mock_graph.aupdate_state = AsyncMock()
    
    with patch.object(chat_worker_module, "AIOKafkaConsumer", return_value=mock_consumer), \
         patch("shared.database.mongodb.MongoDBManager.get_db", return_value=mock_db), \
         patch.object(ai_graph, "get_agent_graph", return_value=mock_graph), \
         patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
         
        # Mock pre-existing conversation metadata
        mock_conversation = {
            "organization_id": "test-org-123",
            "platform": "telegram",
            "bot_name": "TestBot",
            "chat_id": 8888,
            "user": {
                "sender_id": 9999,
                "sender_name": "Alice"
            }
        }
        mock_db.conversations.find_one = AsyncMock(return_value=mock_conversation)
        mock_db.conversations.update_one = AsyncMock()
        
        # Mock Telegram response to be successful
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response
        
        try:
            await worker.start()
        except asyncio.CancelledError:
            pass
            
        # Verify MongoDB was called exactly once (to update updated_at timestamp)
        assert mock_db.conversations.update_one.call_count == 1
        
        # Check update_one arguments
        first_call_args = mock_db.conversations.update_one.call_args_list[0]
        query = first_call_args[0][0]
        update = first_call_args[0][1]
        
        assert query == {"thread_id": "telegram:9999"}
        assert "$set" in update and "updated_at" in update["$set"]
        
        # Verify checkpointer was updated with outbound message
        mock_graph.aupdate_state.assert_called_once()
        call_args = mock_graph.aupdate_state.call_args
        config_arg = call_args[0][0]
        state_update = call_args[0][1]
        assert config_arg == {"configurable": {"thread_id": "telegram:9999"}}
        messages = state_update["messages"]
        assert len(messages) == 1
        assert messages[0].content == "Hello outbound reply"
        
        # Verify Telegram send API was called with the reply
        mock_post.assert_called_once()
        tg_url = mock_post.call_args[0][0]
        tg_json = mock_post.call_args[1]["json"]
        assert tg_url == "https://api.telegram.org/botmock-token/sendMessage"
        assert tg_json["chat_id"] == 8888
        assert tg_json["text"] == "Hello outbound reply"
