"""
summarizer.py
─────────────
Map-reduce summarization:
  1. MAP: Summarize each chunk independently (parallelized)
  2. REDUCE: Combine all chunk summaries into one final summary

This avoids context-window overflow for large documents.
"""

import asyncio
import uuid

from langchain_openai import ChatOpenAI
from langchain.schema import HumanMessage, SystemMessage
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.logging import get_logger
from app.db.models.document import Chunk, Document
from app.services.cache import RedisCache

settings = get_settings()
logger = get_logger(__name__)

MAP_SYSTEM = "You are a precise summarizer. Summarize the following document excerpt in 3-5 sentences. Focus on key facts, arguments, and data."
REDUCE_SYSTEM = "You are a document analyst. Below are summaries of document sections. Synthesize them into a single coherent summary (150-250 words) covering the main themes, key points, and conclusions."

MAX_CONCURRENT_MAP = 5   # parallel OpenAI calls during map phase


class SummarizerService:
    def __init__(
        self,
        db: AsyncSession,
        cache: RedisCache,
        llm: ChatOpenAI | None = None,
    ) -> None:
        self.db = db
        self.cache = cache
        self._llm = llm or ChatOpenAI(
            model=settings.OPENAI_CHAT_MODEL,
            temperature=0.2,
            openai_api_key=settings.OPENAI_API_KEY,
        )

    async def summarize(self, document_id: uuid.UUID) -> tuple[str, bool]:
        """
        Returns (summary_text, was_cached).
        Checks Redis first, then runs map-reduce if needed.
        Also persists the result to the Document row.
        """
        cached = await self.cache.get_summary(str(document_id))
        if cached:
            logger.info("Summary cache hit for document %s", document_id)
            return cached, True

        # Load chunks from DB
        result = await self.db.execute(
            select(Chunk)
            .where(Chunk.document_id == document_id)
            .order_by(Chunk.chunk_index)
        )
        chunks = result.scalars().all()

        if not chunks:
            return "No content available to summarize.", False

        # MAP phase — summarize each chunk in parallel (throttled)
        sem = asyncio.Semaphore(MAX_CONCURRENT_MAP)
        map_tasks = [self._map_chunk(chunk.content, sem) for chunk in chunks]
        chunk_summaries = await asyncio.gather(*map_tasks)

        # REDUCE phase — combine summaries
        combined = "\n\n".join(
            f"Section {i + 1}: {s}" for i, s in enumerate(chunk_summaries) if s
        )
        final_summary = await self._reduce(combined)

        # Persist to DB and cache
        doc_result = await self.db.execute(
            select(Document).where(Document.id == document_id)
        )
        doc = doc_result.scalar_one_or_none()
        if doc:
            doc.summary = final_summary
            await self.db.flush()

        await self.cache.set_summary(str(document_id), final_summary)
        return final_summary, False

    # ─── Map ──────────────────────────────────────────────────────────────────

    async def _map_chunk(self, content: str, sem: asyncio.Semaphore) -> str:
        async with sem:
            try:
                response = await self._llm.ainvoke([
                    SystemMessage(content=MAP_SYSTEM),
                    HumanMessage(content=content[:3000]),  # stay within token budget
                ])
                return response.content.strip()
            except Exception as exc:
                logger.warning("Map summarization failed for chunk: %s", exc)
                return ""

    # ─── Reduce ───────────────────────────────────────────────────────────────

    async def _reduce(self, combined_summaries: str) -> str:
        try:
            response = await self._llm.ainvoke([
                SystemMessage(content=REDUCE_SYSTEM),
                HumanMessage(content=combined_summaries[:8000]),
            ])
            return response.content.strip()
        except Exception as exc:
            logger.error("Reduce summarization failed: %s", exc)
            return "Summary generation failed. Please try again."
