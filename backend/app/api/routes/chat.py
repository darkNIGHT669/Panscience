"""
chat.py
───────
POST /api/chat/sessions                     → create session
GET  /api/chat/sessions                     → list sessions
GET  /api/chat/sessions/{id}/messages       → message history
POST /api/chat/sessions/{id}/messages       → ask a question (SSE stream)
DELETE /api/chat/sessions/{id}              → delete session
"""

import uuid
from collections.abc import AsyncGenerator

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db, get_redis
from app.core.config import get_settings
from app.db.models.chat import ChatSession, Message
from app.db.models.document import Document
from app.db.models.user import User
from app.schemas import ChatRequest, ChatSessionCreate, ChatSessionOut, MessageOut
from app.services.cache import RedisCache
from app.services.embeddings import EmbeddingService
from app.services.rag_pipeline import RAGPipeline

settings = get_settings()
router = APIRouter(prefix="/chat", tags=["chat"])
limiter = Limiter(key_func=get_remote_address)


# ─── Session Management ───────────────────────────────────────────────────────

@router.post("/sessions", response_model=ChatSessionOut, status_code=status.HTTP_201_CREATED)
async def create_session(
    payload: ChatSessionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ChatSession:
    # Verify document exists and belongs to user
    doc_result = await db.execute(
        select(Document).where(
            Document.id == payload.document_id,
            Document.user_id == current_user.id,
        )
    )
    document = doc_result.scalar_one_or_none()
    if not document:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")
    if document.status != "ready":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Document is still processing (status: {document.status}).",
        )

    session = ChatSession(
        user_id=current_user.id,
        document_id=payload.document_id,
        title=payload.title or f"Chat about {document.original_filename}",
    )
    db.add(session)
    await db.flush()
    return session


@router.get("/sessions", response_model=list[ChatSessionOut])
async def list_sessions(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[ChatSession]:
    result = await db.execute(
        select(ChatSession)
        .where(ChatSession.user_id == current_user.id)
        .order_by(ChatSession.created_at.desc())
    )
    return list(result.scalars().all())


@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_session(
    session_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    cache: RedisCache = Depends(get_redis),
) -> None:
    session = await _get_owned_session(db, session_id, current_user.id)
    await cache.clear_chat_history(str(session_id))
    await db.delete(session)


# ─── Message History ──────────────────────────────────────────────────────────

@router.get("/sessions/{session_id}/messages", response_model=list[MessageOut])
async def get_messages(
    session_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[Message]:
    await _get_owned_session(db, session_id, current_user.id)
    result = await db.execute(
        select(Message)
        .where(Message.session_id == session_id)
        .order_by(Message.created_at)
    )
    return list(result.scalars().all())


# ─── Streaming Chat ───────────────────────────────────────────────────────────

@router.post("/sessions/{session_id}/messages")
@limiter.limit(f"{settings.RATE_LIMIT_PER_MINUTE}/minute")
async def send_message(
    request: Request,                               # required by slowapi
    session_id: uuid.UUID,
    payload: ChatRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    cache: RedisCache = Depends(get_redis),
) -> StreamingResponse:
    session = await _get_owned_session(db, session_id, current_user.id)

    # Retrieve chat history from Redis (fast) — fall back to DB if cold
    history = await cache.get_chat_history(str(session_id))
    if not history:
        history = await _load_history_from_db(db, session_id)

    rag = RAGPipeline(db=db, embedding_service=EmbeddingService())

    return StreamingResponse(
        _stream_and_persist(
            rag=rag,
            cache=cache,
            db=db,
            question=payload.question,
            document_id=session.document_id,
            session_id=session_id,
            history=history,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",    # disable Nginx buffering
        },
    )


# ─── Stream + Persist ─────────────────────────────────────────────────────────

async def _stream_and_persist(
    rag: RAGPipeline,
    cache: RedisCache,
    db: AsyncSession,
    question: str,
    document_id: uuid.UUID,
    session_id: uuid.UUID,
    history: list[dict],
) -> AsyncGenerator[str, None]:
    """Streams SSE chunks; collects the full answer and citations; persists to DB + cache."""
    full_answer = []
    citations: list[dict] = []

    # Persist user message
    user_msg = Message(session_id=session_id, role="user", content=question)
    db.add(user_msg)
    await db.flush()

    async for sse_chunk in rag.stream_answer(question, document_id, history):
        yield sse_chunk

        # Parse token/citations for persistence (lightweight JSON parse)
        try:
            import json
            data = json.loads(sse_chunk.removeprefix("data: ").strip())
            if data["type"] == "token":
                full_answer.append(data["data"])
            elif data["type"] == "citations":
                citations = data["data"]
        except Exception:
            pass

    # Persist assistant message
    answer_text = "".join(full_answer)
    assistant_msg = Message(
        session_id=session_id,
        role="assistant",
        content=answer_text,
        citations=citations,
    )
    db.add(assistant_msg)
    await db.commit()

    # Update Redis history
    await cache.append_chat_message(str(session_id), {"role": "user", "content": question})
    await cache.append_chat_message(str(session_id), {"role": "assistant", "content": answer_text})


# ─── Helpers ──────────────────────────────────────────────────────────────────

async def _get_owned_session(
    db: AsyncSession, session_id: uuid.UUID, user_id: uuid.UUID
) -> ChatSession:
    result = await db.execute(
        select(ChatSession).where(
            ChatSession.id == session_id,
            ChatSession.user_id == user_id,
        )
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat session not found.")
    return session


async def _load_history_from_db(db: AsyncSession, session_id: uuid.UUID) -> list[dict]:
    result = await db.execute(
        select(Message)
        .where(Message.session_id == session_id)
        .order_by(Message.created_at)
        .limit(20)
    )
    messages = result.scalars().all()
    return [{"role": m.role, "content": m.content} for m in messages]
