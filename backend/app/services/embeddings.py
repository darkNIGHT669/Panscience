"""
embeddings.py
─────────────
Generates OpenAI embeddings and performs pgvector cosine-similarity search.
Batches requests to respect OpenAI's token limits.
"""

import uuid
from typing import Any

from openai import AsyncOpenAI
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.config import get_settings
from app.core.logging import get_logger
from app.db.models.document import Chunk

settings = get_settings()
logger = get_logger(__name__)

EMBED_BATCH_SIZE = 100   # OpenAI supports up to 2048 inputs per request; keep conservative


class EmbeddingService:
    def __init__(self, client: AsyncOpenAI | None = None) -> None:
        self._client = client or AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

    # ─── Embedding generation ──────────────────────────────────────────────────

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for a list of texts, batching as needed."""
        if not texts:
            return []

        all_embeddings: list[list[float]] = []
        for i in range(0, len(texts), EMBED_BATCH_SIZE):
            batch = texts[i : i + EMBED_BATCH_SIZE]
            batch_embeddings = await self._embed_batch(batch)
            all_embeddings.extend(batch_embeddings)

        return all_embeddings

    async def embed_query(self, query: str) -> list[float]:
        """Embed a single query string."""
        results = await self._embed_batch([query])
        return results[0]

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def _embed_batch(self, texts: list[str]) -> list[list[float]]:
        # Replace newlines — OpenAI recommends this for embedding quality
        cleaned = [t.replace("\n", " ").strip() for t in texts]
        response = await self._client.embeddings.create(
            model=settings.OPENAI_EMBEDDING_MODEL,
            input=cleaned,
            dimensions=settings.OPENAI_EMBEDDING_DIMENSIONS,
        )
        # Sort by index to ensure order is preserved
        sorted_data = sorted(response.data, key=lambda d: d.index)
        return [item.embedding for item in sorted_data]

    # ─── Vector Search ────────────────────────────────────────────────────────

    async def similarity_search(
        self,
        db: AsyncSession,
        query: str,
        document_id: uuid.UUID,
        top_k: int = 5,
    ) -> list[dict[str, Any]]:
        """
        Perform cosine-similarity search in pgvector.
        Returns top_k chunks ranked by relevance.
        """
        query_embedding = await self.embed_query(query)
        embedding_str = f"[{','.join(map(str, query_embedding))}]"

        sql = text("""
            SELECT
                id,
                content,
                chunk_index,
                page_num,
                start_time,
                end_time,
                1 - (embedding <=> :embedding ::vector) AS score
            FROM chunks
            WHERE document_id = :document_id
              AND embedding IS NOT NULL
            ORDER BY embedding <=> :embedding ::vector
            LIMIT :top_k
        """)

        result = await db.execute(
            sql,
            {
                "embedding": embedding_str,
                "document_id": str(document_id),
                "top_k": top_k,
            },
        )
        rows = result.mappings().all()

        return [
            {
                "id": str(row["id"]),
                "content": row["content"],
                "chunk_index": row["chunk_index"],
                "page_num": row["page_num"],
                "start_time": row["start_time"],
                "end_time": row["end_time"],
                "score": float(row["score"]),
            }
            for row in rows
        ]

    async def similarity_search_by_topic(
        self,
        db: AsyncSession,
        topic: str,
        document_id: uuid.UUID,
        top_k: int = 10,
    ) -> list[dict[str, Any]]:
        """
        Topic-specific search — used for the /timestamps endpoint.
        Only returns chunks that have timing information (audio/video).
        """
        query_embedding = await self.embed_query(topic)
        embedding_str = f"[{','.join(map(str, query_embedding))}]"

        sql = text("""
            SELECT
                id,
                content,
                chunk_index,
                start_time,
                end_time,
                1 - (embedding <=> :embedding ::vector) AS score
            FROM chunks
            WHERE document_id = :document_id
              AND embedding IS NOT NULL
              AND start_time IS NOT NULL
            ORDER BY embedding <=> :embedding ::vector
            LIMIT :top_k
        """)

        result = await db.execute(
            sql,
            {
                "embedding": embedding_str,
                "document_id": str(document_id),
                "top_k": top_k,
            },
        )
        rows = result.mappings().all()

        return [
            {
                "id": str(row["id"]),
                "content": row["content"],
                "start_time": float(row["start_time"]),
                "end_time": float(row["end_time"]),
                "score": float(row["score"]),
            }
            for row in rows
        ]
