"""
Tests for /api/documents/* routes.
Covers: upload, list, get, delete, summary, timestamps.
All file I/O and AI services are mocked.
"""

import io
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.document import Document
from app.db.models.user import User


def _make_document(user_id: uuid.UUID, file_type: str = "pdf", status: str = "ready") -> Document:
    return Document(
        user_id=user_id,
        filename="test_doc.pdf",
        original_filename="test_doc.pdf",
        file_type=file_type,
        mime_type="application/pdf" if file_type == "pdf" else "audio/mpeg",
        storage_path="/app/uploads/test/test_doc.pdf",
        file_size_bytes=1024,
        status=status,
    )


@pytest.mark.asyncio
class TestUpload:
    @patch("app.api.routes.upload.FileProcessorService")
    async def test_upload_pdf_success(
        self, mock_processor_cls: MagicMock, client: AsyncClient, test_user: User
    ) -> None:
        mock_doc = _make_document(test_user.id)
        mock_processor_cls.return_value.ingest = AsyncMock(return_value=mock_doc)

        pdf_content = b"%PDF-1.4 fake pdf content"
        response = await client.post(
            "/api/documents/upload",
            files={"file": ("report.pdf", io.BytesIO(pdf_content), "application/pdf")},
        )
        assert response.status_code == 202
        data = response.json()
        assert data["file_type"] == "pdf"
        assert data["status"] == "ready"

    @patch("app.api.routes.upload.FileProcessorService")
    async def test_upload_audio_success(
        self, mock_processor_cls: MagicMock, client: AsyncClient, test_user: User
    ) -> None:
        mock_doc = _make_document(test_user.id, file_type="audio")
        mock_doc.file_type = "audio"
        mock_processor_cls.return_value.ingest = AsyncMock(return_value=mock_doc)

        response = await client.post(
            "/api/documents/upload",
            files={"file": ("podcast.mp3", io.BytesIO(b"fake mp3"), "audio/mpeg")},
        )
        assert response.status_code == 202

    async def test_upload_unsupported_type(self, client: AsyncClient) -> None:
        response = await client.post(
            "/api/documents/upload",
            files={"file": ("script.py", io.BytesIO(b"print('hello')"), "text/x-python")},
        )
        assert response.status_code == 415

    async def test_upload_requires_auth(self, unauthed_client: AsyncClient) -> None:
        response = await unauthed_client.post(
            "/api/documents/upload",
            files={"file": ("test.pdf", io.BytesIO(b"data"), "application/pdf")},
        )
        assert response.status_code == 403


@pytest.mark.asyncio
class TestListDocuments:
    async def test_list_empty(self, client: AsyncClient) -> None:
        response = await client.get("/api/documents/")
        assert response.status_code == 200
        data = response.json()
        assert data["documents"] == []
        assert data["total"] == 0

    async def test_list_with_documents(
        self, client: AsyncClient, db_session: AsyncSession, test_user: User
    ) -> None:
        doc1 = _make_document(test_user.id)
        doc2 = _make_document(test_user.id)
        db_session.add_all([doc1, doc2])
        await db_session.flush()

        response = await client.get("/api/documents/")
        assert response.status_code == 200
        assert response.json()["total"] == 2

    async def test_list_isolates_users(
        self, client: AsyncClient, db_session: AsyncSession, test_user: User
    ) -> None:
        # Add a document for a different user
        other_user = User(
            email="other@example.com",
            hashed_password="hashed",
        )
        db_session.add(other_user)
        await db_session.flush()
        other_doc = _make_document(other_user.id)
        db_session.add(other_doc)
        await db_session.flush()

        response = await client.get("/api/documents/")
        # Should only see test_user's documents (none)
        assert response.json()["total"] == 0


@pytest.mark.asyncio
class TestGetDocument:
    async def test_get_own_document(
        self, client: AsyncClient, db_session: AsyncSession, test_user: User
    ) -> None:
        doc = _make_document(test_user.id)
        db_session.add(doc)
        await db_session.flush()

        response = await client.get(f"/api/documents/{doc.id}")
        assert response.status_code == 200
        assert response.json()["id"] == str(doc.id)

    async def test_get_other_user_document_returns_404(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        other_user = User(email="other2@example.com", hashed_password="h")
        db_session.add(other_user)
        await db_session.flush()
        doc = _make_document(other_user.id)
        db_session.add(doc)
        await db_session.flush()

        response = await client.get(f"/api/documents/{doc.id}")
        assert response.status_code == 404

    async def test_get_nonexistent_document(self, client: AsyncClient) -> None:
        response = await client.get(f"/api/documents/{uuid.uuid4()}")
        assert response.status_code == 404


@pytest.mark.asyncio
class TestDeleteDocument:
    async def test_delete_success(
        self, client: AsyncClient, db_session: AsyncSession, test_user: User
    ) -> None:
        doc = _make_document(test_user.id)
        db_session.add(doc)
        await db_session.flush()

        response = await client.delete(f"/api/documents/{doc.id}")
        assert response.status_code == 204


@pytest.mark.asyncio
class TestSummary:
    @patch("app.api.routes.upload.SummarizerService", create=True)
    async def test_summary_processing_document_returns_409(
        self, client: AsyncClient, db_session: AsyncSession, test_user: User
    ) -> None:
        doc = _make_document(test_user.id, status="processing")
        db_session.add(doc)
        await db_session.flush()

        response = await client.get(f"/api/documents/{doc.id}/summary")
        assert response.status_code == 409

    async def test_summary_returns_cached_if_present(
        self, client: AsyncClient, db_session: AsyncSession, test_user: User
    ) -> None:
        doc = _make_document(test_user.id)
        doc.summary = "Pre-computed summary text."
        db_session.add(doc)
        await db_session.flush()

        response = await client.get(f"/api/documents/{doc.id}/summary")
        assert response.status_code == 200
        data = response.json()
        assert data["summary"] == "Pre-computed summary text."
        assert data["cached"] is True


@pytest.mark.asyncio
class TestTimestamps:
    async def test_timestamps_on_pdf_returns_400(
        self, client: AsyncClient, db_session: AsyncSession, test_user: User
    ) -> None:
        doc = _make_document(test_user.id, file_type="pdf")
        db_session.add(doc)
        await db_session.flush()

        response = await client.get(f"/api/documents/{doc.id}/timestamps?topic=neural+networks")
        assert response.status_code == 400

    @patch("app.api.routes.upload.EmbeddingService")
    async def test_timestamps_on_audio(
        self,
        mock_emb_cls: MagicMock,
        client: AsyncClient,
        db_session: AsyncSession,
        test_user: User,
        mock_embedding_service,
    ) -> None:
        mock_emb_cls.return_value = mock_embedding_service
        doc = _make_document(test_user.id, file_type="audio")
        db_session.add(doc)
        await db_session.flush()

        response = await client.get(f"/api/documents/{doc.id}/timestamps?topic=neural+networks")
        assert response.status_code == 200
        data = response.json()
        assert "results" in data
        assert data["topic"] == "neural networks"
