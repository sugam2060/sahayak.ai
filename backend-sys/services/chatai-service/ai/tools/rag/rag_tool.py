"""
Tool: Search the organization's knowledge base via Pinecone.
Uses Pinecone's built-in inference embedding for query vectorization.
"""
import logging
from typing import Annotated
from langchain_core.tools import tool
from langgraph.prebuilt import InjectedState
from pinecone import Pinecone
from shared.config import PINECONE_API_KEY, PINECONE_INDEX_HOST

logger = logging.getLogger("chatai_service.ai.tools.rag.rag_tool")

# Pinecone built-in inference embedding model
EMBEDDING_MODEL = "multilingual-e5-large"

# Lazy singleton
_pc_client = None
_index = None


def _get_pinecone_index():
    """Lazily initialize the Pinecone client and index."""
    global _pc_client, _index
    if _index is None:
        if not PINECONE_API_KEY or not PINECONE_INDEX_HOST:
            raise ValueError("PINECONE_API_KEY and PINECONE_INDEX_HOST must be configured.")
        _pc_client = Pinecone(api_key=PINECONE_API_KEY)
        _index = _pc_client.Index(host=PINECONE_INDEX_HOST)
    return _index


@tool
async def search_knowledge_base(
    query: str,
    organization_id: Annotated[str, InjectedState("organization_id")]
) -> str:
    """Search the organization's knowledge base for relevant information to answer customer questions.
    Always use this tool first when you need to answer questions about products, policies, services, or any organization-specific information.
    
    Args:
        query: The search query describing what information to find.
        organization_id: The organization's UUID to filter results (injected from state).
    """
    try:
        index = _get_pinecone_index()
        
        # Use Pinecone's integrated inference for embedding
        results = index.search(
            namespace=organization_id,
            query={
                "top_k": 5,
                "inputs": {"text": query},
                "filter": {"organization_id": {"$eq": organization_id}}
            }
        )
        
        if not results or not results.get("result", {}).get("hits"):
            # Fallback: try default namespace
            results = index.search(
                namespace="__default__",
                query={
                    "top_k": 5,
                    "inputs": {"text": query},
                    "filter": {"organization_id": {"$eq": organization_id}}
                }
            )
        
        hits = results.get("result", {}).get("hits", [])
        
        if not hits:
            return "No relevant information found in the knowledge base for this query."
        
        # Extract and format the matched chunks
        context_parts = []
        for i, hit in enumerate(hits, 1):
            fields = hit.get("fields", {})
            text = fields.get("text", fields.get("chunk_text", ""))
            score = hit.get("_score", 0)
            if text and score > 0.15:  # Relevance threshold adjusted for e5 embeddings
                context_parts.append(f"[{i}] {text}")
        
        if not context_parts:
            return "No sufficiently relevant information found in the knowledge base."
        
        return "Knowledge Base Results:\n\n" + "\n\n".join(context_parts)
    except Exception as e:
        logger.error(f"Error searching knowledge base: {e}", exc_info=True)
        return f"Error searching knowledge base: {str(e)}"
