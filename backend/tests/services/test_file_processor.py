"""
Unit tests for FileProcessorService.
PDF extraction uses real PyMuPDF on minimal in-memory PDFs.
Media processing mocks Whisper API.
"""

import io
import uuid
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.file_processor import FileProcessorService


def _make_service(db=None, emb=None, tr=None) -> FileProcessorService:
    return FileProcessorService(
        db=db or AsyncMock(),
        embedding_service=emb or AsyncMock(),
        transcription_service=tr or AsyncMock(),
    )


@pytest.mark.asyncio
class TestSafeFilename:
    def test_strips_path_traversal(self) -> None:
        result = FileProcessorService._safe_filename("../../etc/passwd")
        assert ".." not in result
        assert "/" not in result

    def test_replaces_spaces(self) -> None:
        result = FileProcessorService._safe_filename("my document.pdf")
        assert " " not in result

    def test_preserves_extension(self) -> None:
        result = FileProcessorService._safe_filename("report.pdf")
        assert result.endswith(".pdf")

    def test_truncates_long_stem(self) -> None:
        long_name = "a" * 200 + ".mp3"
        result = FileProcessorService._safe_filename(long_name)
        assert len(result) < 120  # 100 stem + extension

    def test_handles_no_extension(self) -> None:
        result = FileProcessorService._safe_filename("noextension")
        assert result  # Should not crash


@pytest.mark.asyncio
class TestResolveFileType:
    def test_pdf_mime(self) -> None:
        svc = _make_service()
        assert svc._resolve_file_type("application/pdf") == "pdf"

    def test_mp3_mime(self) -> None:
        svc = _make_service()
        assert svc._resolve_file_type("audio/mpeg") == "audio"

    def test_mp4_video_mime(self) -> None:
        svc = _make_service()
        assert svc._resolve_file_type("video/mp4") == "video"

    def test_unsupported_mime_raises(self) -> None:
        svc = _make_service()
        with pytest.raises(ValueError, match="Unsupported"):
            svc._resolve_file_type("text/plain")

    def test_wav_mime(self) -> None:
        svc = _make_service()
        assert svc._resolve_file_type("audio/wav") == "audio"


@pytest.mark.asyncio
class TestMediaChunking:
    async def test_media_chunks_group_segments(self) -> None:
        mock_tr = AsyncMock()
        mock_tr.transcribe.return_value = {
            "text": "Hello world this is a test.",
            "segments": [
                {"id": i, "start": float(i * 5), "end": float(i * 5 + 5), "text": f"Segment {i}."}
                for i in range(10)  # 50 seconds total
            ],
            "duration": 50.0,
        }

        svc = _make_service(tr=mock_tr)
        chunks, duration = await svc._process_media(Path("fake.mp3"))

        # With AUDIO_CHUNK_SECONDS=30, 50 seconds should produce at least 1 chunk
        assert len(chunks) >= 1
        assert duration == 50.0
        for chunk in chunks:
            assert chunk["start_time"] is not None
            assert chunk["end_time"] is not None
            assert chunk["page_num"] is None

    async def test_media_chunks_have_correct_timing(self) -> None:
        mock_tr = AsyncMock()
        mock_tr.transcribe.return_value = {
            "text": "Content.",
            "segments": [
                {"id": 0, "start": 0.0, "end": 30.0, "text": "First thirty seconds."},
                {"id": 1, "start": 30.0, "end": 60.0, "text": "Second thirty seconds."},
            ],
            "duration": 60.0,
        }

        svc = _make_service(tr=mock_tr)
        chunks, duration = await svc._process_media(Path("fake.mp4"))

        assert any(c["start_time"] == 0.0 for c in chunks)

    async def test_empty_segments_produces_no_chunks(self) -> None:
        mock_tr = AsyncMock()
        mock_tr.transcribe.return_value = {
            "text": "",
            "segments": [],
            "duration": 0.0,
        }

        svc = _make_service(tr=mock_tr)
        chunks, duration = await svc._process_media(Path("silent.mp3"))
        assert chunks == []
        assert duration == 0.0


@pytest.mark.asyncio
class TestStoreChunks:
    async def test_store_chunks_calls_embed_texts(self) -> None:
        mock_db = AsyncMock()
        mock_emb = AsyncMock()
        mock_emb.embed_texts.return_value = [[0.1] * 1536, [0.2] * 1536]

        svc = _make_service(db=mock_db, emb=mock_emb)
        chunks_data = [
            {"content": "chunk one", "chunk_index": 0, "page_num": 1, "start_time": None, "end_time": None},
            {"content": "chunk two", "chunk_index": 1, "page_num": 2, "start_time": None, "end_time": None},
        ]

        await svc._store_chunks(mock_db, uuid.uuid4(), chunks_data)
        mock_emb.embed_texts.assert_called_once_with(["chunk one", "chunk two"])
        assert mock_db.add_all.called

    async def test_store_chunks_handles_empty_input(self) -> None:
        mock_db = AsyncMock()
        mock_emb = AsyncMock()
        mock_emb.embed_texts.return_value = []

        svc = _make_service(db=mock_db, emb=mock_emb)
        await svc._store_chunks(mock_db, uuid.uuid4(), [])

        mock_emb.embed_texts.assert_called_once_with([])
