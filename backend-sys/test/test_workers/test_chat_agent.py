import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from shared.database.schema.chat_message_mongo import MessageIntent
import importlib

embeddings = importlib.import_module("services.chatai-service.ai.embeddings")
cosine_similarity = embeddings.cosine_similarity
EmbeddingService = embeddings.EmbeddingService
save_message_embedding = embeddings.save_message_embedding
search_semantic_context = embeddings.search_semantic_context

memory = importlib.import_module("services.chatai-service.ai.memory")
summarize_history = memory.summarize_history
compress_conversation_history = memory.compress_conversation_history

state_module = importlib.import_module("services.chatai-service.ai.state")
CustomerState = state_module.CustomerState

@pytest.mark.asyncio
async def test_cosine_similarity():
    v1 = [1.0, 0.0, 0.0]
    v2 = [1.0, 0.0, 0.0]
    assert cosine_similarity(v1, v2) == pytest.approx(1.0)
    
    v3 = [0.0, 1.0, 0.0]
    assert cosine_similarity(v1, v3) == pytest.approx(0.0)

@pytest.mark.asyncio
async def test_embedding_service_fallback():
    # Mocking HF API error to check offline trigram fallback
    with patch("httpx.AsyncClient.post", side_effect=Exception("HF API Down")):
        emb = await EmbeddingService.get_embedding("hello world")
        assert len(emb) == 384
        # Verify it's normalized
        norm = sum(x*x for x in emb)
        assert norm == pytest.approx(1.0)

@pytest.mark.asyncio
async def test_memory_summarization_triggers_on_eight():
    import os
    os.environ["GROQ_API_KEY"] = "fake-key"
    mock_db = MagicMock()
    mock_db.conversations = AsyncMock()
    
    # 8 messages inside history
    mock_messages = [
        {"message_id": i, "direction": "inbound", "sender_name": "User", "text": f"Msg {i}"}
        for i in range(1, 9)
    ]
    
    mock_conversation = {
        "_id": "dummy_id",
        "platform": "telegram",
        "user": {"sender_id": 1234},
        "messages": mock_messages,
        "previous_summary": "Some old summary"
    }
    mock_db.conversations.find_one.return_value = mock_conversation
    
    # Mock ChatGroq to return summary
    mock_llm_response = MagicMock()
    mock_llm_response.content = "New Summary details"
    
    with patch("shared.database.mongodb.MongoDBManager.get_db", return_value=mock_db), \
         patch("langchain_groq.ChatGroq.ainvoke", new_callable=AsyncMock, return_value=mock_llm_response), \
         patch.object(memory, "save_message_embedding", new_callable=AsyncMock) as mock_archive:
         
        await compress_conversation_history(1234, "telegram")
        
        # Verify summarize_history was triggered
        assert mock_archive.call_count == 6  # Oldest 6 messages archived in RAG
        
        # Verify MongoDB updated keeping last 2 active messages
        mock_db.conversations.update_one.assert_called_once()
        update_args = mock_db.conversations.update_one.call_args[0][1]
        assert update_args["$set"]["previous_summary"] == "New Summary details"
        assert len(update_args["$set"]["messages"]) == 2
        assert update_args["$set"]["messages"][0]["message_id"] == 7
        assert update_args["$set"]["messages"][1]["message_id"] == 8

@pytest.mark.asyncio
async def test_graph_routing_decision():
    graph_module = importlib.import_module("services.chatai-service.ai.graph")
    route_by_intent = graph_module.route_by_intent
    
    # Buy intent should route to sales agent
    state_buy = {
        "intent": MessageIntent.BUY,
        "handoff_requested": False,
        "messages": []
    }
    assert route_by_intent(state_buy) == "sales_agent"
    
    # No intent should route to support agent
    state_support = {
        "intent": MessageIntent.NO_INTENT,
        "handoff_requested": False,
        "messages": []
    }
    assert route_by_intent(state_support) == "support_agent"
    
    # Manual keyword trigger should route to handoff
    from langchain_core.messages import HumanMessage
    state_manual = {
        "intent": MessageIntent.BUY,
        "handoff_requested": False,
        "messages": [HumanMessage(content="i want to talk to a human agent please")]
    }
    assert route_by_intent(state_manual) == "handoff_agent"
    
    # Handoff flag should route to handoff
    state_flag = {
        "intent": MessageIntent.BUY,
        "handoff_requested": True,
        "messages": []
    }
    assert route_by_intent(state_flag) == "handoff_agent"
