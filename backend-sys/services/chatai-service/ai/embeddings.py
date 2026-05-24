import os
import math
import httpx
import logging
from datetime import datetime, timezone
from shared.database.mongodb import MongoDBManager

logger = logging.getLogger("chatai_service.embeddings")

class EmbeddingService:
    @staticmethod
    async def get_embedding(text: str) -> list[float]:
        """
        Generate a vector embedding for the given text.
        Tries OpenAI first if OPENAI_API_KEY is in env, otherwise HuggingFace API,
        with a deterministic local fallback.
        """
        if not text:
            return [0.0] * 384
            
        openai_key = os.getenv("OPENAI_API_KEY")
        if openai_key:
            try:
                async with httpx.AsyncClient() as client:
                    resp = await client.post(
                        "https://api.openai.com/v1/embeddings",
                        headers={
                            "Authorization": f"Bearer {openai_key}",
                            "Content-Type": "application/json"
                        },
                        json={
                            "input": text,
                            "model": "text-embedding-3-small"
                        },
                        timeout=5.0
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        return data["data"][0]["embedding"]
                    else:
                        logger.warning(f"OpenAI embedding failed: {resp.status_code} - {resp.text}")
            except Exception as e:
                logger.warning(f"OpenAI embedding error: {e}")
                
        # Fallback to HuggingFace Free Inference API (384 dimensions)
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    "https://api-inference.huggingface.co/pipeline/feature-extraction/sentence-transformers/all-MiniLM-L6-v2",
                    json={"inputs": [text]},
                    timeout=5.0
                )
                if resp.status_code == 200:
                    emb = resp.json()
                    if isinstance(emb, list) and len(emb) > 0:
                        # Sometimes HF returns a nested list: [[[val, ...]]] or [[val, ...]]
                        val = emb[0]
                        while isinstance(val, list):
                            val = val[0]
                        if isinstance(val, (int, float)):
                            flat = emb
                            while isinstance(flat[0], list):
                                flat = flat[0]
                            return [float(x) for x in flat]
        except Exception as e:
            logger.warning(f"HuggingFace embedding error: {e}")
            
        # Offline/failure fallback: simple bag-of-words / trigram hash embedding (384 dimensions)
        vector = [0.0] * 384
        for i, char in enumerate(text):
            idx = hash(char + str(i % 10)) % 384
            vector[idx] += 1.0
        norm = math.sqrt(sum(x * x for x in vector))
        if norm > 0:
            vector = [x / norm for x in vector]
        return vector

def cosine_similarity(v1: list[float], v2: list[float]) -> float:
    if len(v1) != len(v2):
        min_len = min(len(v1), len(v2))
        v1 = v1[:min_len]
        v2 = v2[:min_len]
        
    dot_product = sum(x * y for x, y in zip(v1, v2))
    magnitude1 = math.sqrt(sum(x * x for x in v1))
    magnitude2 = math.sqrt(sum(x * x for x in v2))
    if not magnitude1 or not magnitude2:
        return 0.0
    return dot_product / (magnitude1 * magnitude2)

async def save_message_embedding(sender_id: int, platform: str, text: str):
    """
    Generate embedding and store the message in the MongoDB chat_vector_store.
    """
    if not text.strip():
        return
        
    try:
        embedding = await EmbeddingService.get_embedding(text)
        db = MongoDBManager.get_db()
        await db.chat_vector_store.insert_one({
            "sender_id": sender_id,
            "platform": platform.lower(),
            "text": text,
            "embedding": embedding,
            "created_at": datetime.now(timezone.utc)
        })
        logger.debug(f"Saved embedding for sender_id {sender_id} to chat_vector_store.")
    except Exception as e:
        logger.error(f"Failed to save message embedding: {e}")

async def search_semantic_context(sender_id: int, platform: str, query: str, limit: int = 3) -> list[str]:
    """
    Search for similar past messages from the chat_vector_store using cosine similarity.
    """
    if not query.strip():
        return []
        
    try:
        query_vector = await EmbeddingService.get_embedding(query)
        db = MongoDBManager.get_db()
        
        # Retrieve all documents for this sender and platform
        cursor = db.chat_vector_store.find({
            "sender_id": sender_id,
            "platform": platform.lower()
        })
        
        matches = []
        async for doc in cursor:
            text = doc.get("text", "")
            embedding = doc.get("embedding")
            if text and embedding:
                sim = cosine_similarity(query_vector, embedding)
                matches.append((sim, text))
                
        matches.sort(key=lambda x: x[0], reverse=True)
        return [text for sim, text in matches[:limit] if sim > 0.35]
    except Exception as e:
        logger.error(f"Failed to perform semantic search: {e}")
        return []
