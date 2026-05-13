"""
Integration tests for the chat streaming endpoint.
Tests the full SSE flow: create session → send message → parse stream.
"""

import json
import uuid
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.chat import ChatSession
from app.db.models.document import Document
from app.db.models.user import User


def _make_ready_document(user_id: uuid.UUID) -> Document:
    return Document(
        user_id=user_id,
        filename="lecture.mp4",
        original_filename="lecture.mp4",
        file_type="video",
        mime_type="video/mp4",
        storage_path="/app/uploads/test/lecture.mp4",
        file_size_bytes=10_000_000,
        status="ready",
        duration_seconds=1800.0,
    )


@pytest.mark.asyncio
class TestChatSession:
    async def test_create_session_success(
        self, client: AsyncClient, db_session: AsyncSession, test_user: User
    ) -> None:
        doc = _make_ready_document(test_user.id)
        db_session.add(doc)
        await db_session.flush()

        response = await client.post(
            "/api/chat/sessions",
            json={"document_id": str(doc.id)},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["document_id"] == str(doc.id)
        assert "id" in data

    async def test_create_session_processing_document_fails(
        self, client: AsyncClient, db_session: AsyncSession, test_user: User
    ) -> None:
        doc = _make_ready_document(test_user.id)
        doc.status = "processing"
        db_session.add(doc)
        await db_session.flush()

        response = await client.post(
            "/api/chat/sessions",
            json={"document_id": str(doc.id)},
        )
        assert response.status_code == 409

    async def test_list_sessions(
        self, client: AsyncClient, db_session: AsyncSession, test_user: User
    ) -> None:
        doc = _make_ready_document(test_user.id)
        db_session.add(doc)
        await db_session.flush()

        session = ChatSession(user_id=test_user.id, document_id=doc.id, title="Test Chat")
        db_session.add(session)
        await db_session.flush()

        response = await client.get("/api/chat/sessions")
        assert response.status_code == 200
        sessions = response.json()
        assert len(sessions) == 1
        assert sessions[0]["title"] == "Test Chat"

    async def test_delete_session(
        self, client: AsyncClient, db_session: AsyncSession, test_user: User, mock_redis
    ) -> None:
        doc = _make_ready_document(test_user.id)
        db_session.add(doc)
        await db_session.flush()

        session = ChatSession(user_id=test_user.id, document_id=doc.id)
        db_session.add(session)
        await db_session.flush()

        response = await client.delete(f"/api/chat/sessions/{session.id}")
        assert response.status_code == 204
        mock_redis.clear_chat_history.assert_called_once_with(str(session.id))

    async def test_delete_session_not_found(self, client: AsyncClient) -> None:
        response = await client.delete(f"/api/chat/sessions/{uuid.uuid4()}")
        assert response.status_code == 404


@pytest.mark.asyncio
class TestStreamingChat:
    async def test_send_message_streams_sse(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_user: User,
        mock_redis,
    ) -> None:
        doc = _make_ready_document(test_user.id)
        db_session.add(doc)
        await db_session.flush()

        session = ChatSession(user_id=test_user.id, document_id=doc.id)
        db_session.add(session)
        await db_session.flush()

        async def fake_stream(*args, **kwargs):
            yield f"data: {json.dumps({'type': 'token', 'data': 'Neural '})}\n\n"
            yield f"data: {json.dumps({'type': 'token', 'data': 'networks'})}\n\n"
            yield f"data: {json.dumps({'type': 'citations', 'data': []})}\n\n"
            yield f"data: {json.dumps({'type': 'done', 'data': None})}\n\n"

        with patch("app.api.routes.chat.RAGPipeline") as mock_rag_cls:
            mock_rag_cls.return_value.stream_answer = fake_stream

            response = await client.post(
                f"/api/chat/sessions/{session.id}/messages",
                json={"question": "What are neural networks?"},
            )

        assert response.status_code == 200
        assert "text/event-stream" in response.headers["content-type"]

        events = [
            json.loads(line.removeprefix("data: "))
            for line in response.text.split("\n\n")
            if line.startswith("data:")
        ]
        token_events = [e for e in events if e["type"] == "token"]
        assert len(token_events) == 2
        assert token_events[0]["data"] == "Neural "

        done_events = [e for e in events if e["type"] == "done"]
        assert len(done_events) == 1

    async def test_get_message_history(
        self, client: AsyncClient, db_session: AsyncSession, test_user: User
    ) -> None:
        from app.db.models.chat import Message

        doc = _make_ready_document(test_user.id)
        db_session.add(doc)
        await db_session.flush()

        session = ChatSession(user_id=test_user.id, document_id=doc.id)
        db_session.add(session)
        await db_session.flush()

        msg = Message(session_id=session.id, role="user", content="Hello")
        db_session.add(msg)
        await db_session.flush()

        response = await client.get(f"/api/chat/sessions/{session.id}/messages")
        assert response.status_code == 200
        messages = response.json()
        assert len(messages) == 1
        assert messages[0]["content"] == "Hello"
        assert messages[0]["role"] == "user"

    async def test_send_message_empty_question_returns_422(
        self, client: AsyncClient, db_session: AsyncSession, test_user: User
    ) -> None:
        doc = _make_ready_document(test_user.id)
        db_session.add(doc)
        await db_session.flush()

        session = ChatSession(user_id=test_user.id, document_id=doc.id)
        db_session.add(session)
        await db_session.flush()

        response = await client.post(
            f"/api/chat/sessions/{session.id}/messages",
            json={"question": ""},
        )
        assert response.status_code == 422
