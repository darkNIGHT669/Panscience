"""
rag_pipeline.py
───────────────
LangChain RAG chain that:
  1. Retrieves top-K chunks via pgvector similarity search
  2. Streams the GPT-4o answer token-by-token via AsyncIteratorCallbackHandler
  3. Returns structured citations (chunk_id, page_num, start_time, end_time)

The chain is stateless — chat history is passed in from Redis on every call.
"""

import asyncio
import json
import uuid
from collections.abc import AsyncGenerator
from typing import Any

from langchain.callbacks.streaming_aiter import AsyncIteratorCallbackHandler
from langchain.schema import AIMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.logging import get_logger
from app.services.embeddings import EmbeddingService

settings = get_settings()
logger = get_logger(__name__)

SYSTEM_PROMPT = """You are a precise, expert document analyst. Your job is to answer questions \
using ONLY the context provided below. If the answer is not in the context, say so clearly.

Rules:
- Be concise and direct.
- Always ground your answer in the provided context.
- When referring to specific passages, note their source (page number or timestamp).
- Never fabricate information not present in the context.

Context:
{context}
"""


class RAGPipeline:
    def __init__(
        self,
        db: AsyncSession,
        embedding_service: EmbeddingService,
        llm: ChatOpenAI | None = None,
    ) -> None:
        self.db = db
        self.embedding_service = embedding_service
        self._llm = llm or ChatOpenAI(
            model=settings.OPENAI_CHAT_MODEL,
            temperature=0.1,
            streaming=True,
            openai_api_key=settings.OPENAI_API_KEY,
        )

    # ─── Public: streaming answer ──────────────────────────────────────────────

    async def stream_answer(
        self,
        question: str,
        document_id: uuid.UUID,
        chat_history: list[dict],
    ) -> AsyncGenerator[str, None]:
        """
        Yields Server-Sent Event strings:
          data: {"type": "token",     "data": "<token>"}
          data: {"type": "citations", "data": [{...}]}
          data: {"type": "done",      "data": null}
          data: {"type": "error",     "data": "<message>"}
        """
        try:
            # 1. Retrieve relevant chunks
            chunks = await self.embedding_service.similarity_search(
                db=self.db,
                query=question,
                document_id=document_id,
                top_k=settings.TOP_K_RETRIEVAL,
            )

            if not chunks:
                yield _sse({"type": "token", "data": "I couldn't find relevant content in the document to answer your question."})
                yield _sse({"type": "citations", "data": []})
                yield _sse({"type": "done", "data": None})
                return

            # 2. Build context block with source labels
            context_parts = []
            for i, chunk in enumerate(chunks):
                label = _chunk_label(chunk, i)
                context_parts.append(f"[{label}]\n{chunk['content']}")
            context = "\n\n---\n\n".join(context_parts)

            # 3. Build message list
            messages = [SystemMessage(content=SYSTEM_PROMPT.format(context=context))]
            for msg in chat_history[-10:]:   # last 10 messages for context window budget
                if msg["role"] == "user":
                    messages.append(HumanMessage(content=msg["content"]))
                elif msg["role"] == "assistant":
                    messages.append(AIMessage(content=msg["content"]))
            messages.append(HumanMessage(content=question))

            # 4. Stream tokens via callback handler
            callback = AsyncIteratorCallbackHandler()
            llm_with_callback = self._llm.bind(callbacks=[callback])

            async def _run_llm() -> None:
                await llm_with_callback.ainvoke(messages)

            task = asyncio.create_task(_run_llm())

            async for token in callback.aiter():
                yield _sse({"type": "token", "data": token})

            await task  # ensure exceptions surface

            # 5. Emit citations after streaming completes
            citations = _build_citations(chunks)
            yield _sse({"type": "citations", "data": citations})
            yield _sse({"type": "done", "data": None})

        except asyncio.CancelledError:
            logger.info("Stream cancelled by client")
        except Exception as exc:
            logger.exception("RAG pipeline error: %s", exc)
            yield _sse({"type": "error", "data": str(exc)})

    # ─── Public: non-streaming answer (for testing / summary) ─────────────────

    async def get_answer(
        self,
        question: str,
        document_id: uuid.UUID,
        chat_history: list[dict] | None = None,
    ) -> dict[str, Any]:
        """Returns {"answer": str, "citations": list[dict]}."""
        chunks = await self.embedding_service.similarity_search(
            db=self.db,
            query=question,
            document_id=document_id,
            top_k=settings.TOP_K_RETRIEVAL,
        )

        context_parts = [
            f"[{_chunk_label(chunk, i)}]\n{chunk['content']}"
            for i, chunk in enumerate(chunks)
        ]
        context = "\n\n---\n\n".join(context_parts)

        messages = [SystemMessage(content=SYSTEM_PROMPT.format(context=context))]
        for msg in (chat_history or [])[-10:]:
            if msg["role"] == "user":
                messages.append(HumanMessage(content=msg["content"]))
            elif msg["role"] == "assistant":
                messages.append(AIMessage(content=msg["content"]))
        messages.append(HumanMessage(content=question))

        response = await self._llm.ainvoke(messages)
        return {
            "answer": response.content,
            "citations": _build_citations(chunks),
        }


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _sse(payload: dict) -> str:
    """Format a dict as an SSE data line."""
    return f"data: {json.dumps(payload)}\n\n"


def _chunk_label(chunk: dict, index: int) -> str:
    if chunk.get("page_num") is not None:
        return f"Source {index + 1} — Page {chunk['page_num']}"
    if chunk.get("start_time") is not None:
        start = _fmt_time(chunk["start_time"])
        end = _fmt_time(chunk.get("end_time", chunk["start_time"]))
        return f"Source {index + 1} — {start}–{end}"
    return f"Source {index + 1}"


def _build_citations(chunks: list[dict]) -> list[dict]:
    return [
        {
            "chunk_id": chunk["id"],
            "page_num": chunk.get("page_num"),
            "start_time": chunk.get("start_time"),
            "end_time": chunk.get("end_time"),
            "text_snippet": chunk["content"][:200] + "…" if len(chunk["content"]) > 200 else chunk["content"],
        }
        for chunk in chunks
    ]


def _fmt_time(seconds: float) -> str:
    minutes = int(seconds) // 60
    secs = int(seconds) % 60
    return f"{minutes:02d}:{secs:02d}"
