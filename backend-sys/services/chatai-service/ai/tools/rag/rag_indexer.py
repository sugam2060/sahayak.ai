"""
RAG knowledge base indexer.
Upserts organization knowledge base text into Pinecone
using Pinecone's built-in inference embeddings.

Called from the AI config update endpoint when knowledge_base changes.
"""
import logging
import hashlib
from pinecone import Pinecone
from shared.config import PINECONE_API_KEY, PINECONE_INDEX_HOST

logger = logging.getLogger("chatai_service.ai.tools.rag.rag_indexer")

# Chunk configuration
CHUNK_SIZE = 500  # Characters per chunk
CHUNK_OVERLAP = 50  # Overlap between chunks


def _chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """
    Split text into overlapping chunks for better retrieval.
    Tries to split on sentence boundaries when possible.
    """
    if not text or not text.strip():
        return []
    
    text = text.strip()
    
    # If text is small enough, return as single chunk
    if len(text) <= chunk_size:
        return [text]
    
    chunks = []
    start = 0
    
    while start < len(text):
        end = start + chunk_size
        
        if end >= len(text):
            chunks.append(text[start:].strip())
            break
        
        # Try to find a sentence boundary (., !, ?, \n) near the end
        boundary = -1
        for sep in ['. ', '.\n', '!\n', '?\n', '! ', '? ', '\n\n', '\n']:
            pos = text.rfind(sep, start + chunk_size // 2, end)
            if pos > boundary:
                boundary = pos + len(sep)
        
        if boundary > start:
            chunks.append(text[start:boundary].strip())
            start = boundary - overlap
        else:
            # No sentence boundary found, split at word boundary
            space_pos = text.rfind(' ', start + chunk_size // 2, end)
            if space_pos > start:
                chunks.append(text[start:space_pos].strip())
                start = space_pos + 1 - overlap
            else:
                chunks.append(text[start:end].strip())
                start = end - overlap
    
    return [c for c in chunks if c]


def _generate_chunk_id(org_id: str, chunk_index: int) -> str:
    """Generate a deterministic ID for a chunk based on org_id and index."""
    raw = f"{org_id}:chunk:{chunk_index}"
    return hashlib.md5(raw.encode()).hexdigest()


async def upsert_knowledge_base(
    organization_id: str,
    organization_name: str,
    knowledge_text: str
) -> None:
    """
    Upsert knowledge base text into Pinecone with organization metadata.
    
    1. Delete all existing vectors for this organization
    2. Split the knowledge text into chunks
    3. Upsert new vectors using Pinecone's integrated inference
    
    Args:
        organization_id: Organization UUID string
        organization_name: Organization display name
        knowledge_text: Raw knowledge base text to index
    """
    if not PINECONE_API_KEY or not PINECONE_INDEX_HOST:
        logger.warning("Pinecone not configured. Skipping knowledge base indexing.")
        return
    
    try:
        pc = Pinecone(api_key=PINECONE_API_KEY)
        index = pc.Index(host=PINECONE_INDEX_HOST)
        
        # Step 1: Delete existing vectors for this organization
        try:
            index.delete(
                namespace=organization_id,
                delete_all=True
            )
            logger.info(f"Cleared existing knowledge base vectors for org {organization_id}")
        except Exception as e:
            logger.warning(f"Error clearing existing vectors (may not exist): {e}")
        
        # Step 2: If knowledge text is empty, we're done (just cleared)
        if not knowledge_text or not knowledge_text.strip():
            logger.info(f"Empty knowledge base for org {organization_id}. Cleared index.")
            return
        
        # Step 3: Chunk the text
        chunks = _chunk_text(knowledge_text)
        if not chunks:
            logger.info(f"No chunks generated for org {organization_id}.")
            return
        
        # Step 4: Upsert using Pinecone's integrated inference
        records = []
        for i, chunk in enumerate(chunks):
            record = {
                "id": _generate_chunk_id(organization_id, i),
                "_text": chunk,  # Pinecone inference field
                "organization_id": organization_id,
                "organization_name": organization_name,
                "chunk_index": i,
                "text": chunk,  # Stored as metadata for retrieval
            }
            records.append(record)
        
        # Upsert in batches of 96 (Pinecone's recommended batch size)
        batch_size = 96
        for batch_start in range(0, len(records), batch_size):
            batch = records[batch_start:batch_start + batch_size]
            index.upsert_records(
                namespace=organization_id,
                records=batch
            )
        
        logger.info(
            f"Successfully indexed {len(chunks)} chunks for org {organization_id} "
            f"({organization_name})"
        )
    except Exception as e:
        logger.error(f"Error indexing knowledge base for org {organization_id}: {e}", exc_info=True)
        raise
