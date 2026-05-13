"""
Unit tests for all backend services.
All external APIs (OpenAI, Whisper) are mocked.
"""

import io
import uuid
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, mock_open, patch

import pytest

from app.services.cache import RedisCache
from app.services.embeddings import EmbeddingService
from app.services.rag_pipeline import RAGPipeline, _fmt_time, _build_citations, _chunk_label
from app.services.summarizer import SummarizerService
from app.services.transcription import TranscriptionService


# ════════════════════════════════════════════════════════════
# TranscriptionService
# ════════════════════════════════════════════════════════════

@pytest.mark.asyncio
class TestTranscriptionService:
    def _make_whisper_response(self) -> MagicMock:
        seg = MagicMock()
        seg.id = 0
        seg.start = 0.0
        seg.end = 5.5
        seg.text = "Hello world"

        response = MagicMock()
        response.text = "Hello world"
        response.duration = 5.5
        response.language = "en"
        response.model_dump.return_value = {
            "text": "Hello world",
            "duration": 5.5,
            "language": "en",
            "segments": [{"id": 0, "start": 0.0, "end": 5.5, "text": "Hello world"}],
        }
        return response

    async def test_transcribe_small_file(self, tmp_path: Path) -> None:
        audio_file = tmp_path / "test.mp3"
        audio_file.write_bytes(b"fake audio data" * 100)

        mock_client = AsyncMock()
        mock_client.audio.transcriptions.create.return_value = self._make_whisper_response()

        service = TranscriptionService(client=mock_client)
        result = await service.transcribe(audio_file)

        assert result["text"] == "Hello world"
        assert len(result["segments"]) == 1
        assert result["segments"][0]["start"] == 0.0
        assert result["duration"] == 5.5
        mock_client.audio.transcriptions.create.assert_called_once()

    async def test_transcribe_returns_normalized_segments(self, tmp_path: Path) -> None:
        audio_file = tmp_path / "test.mp3"
        audio_file.write_bytes(b"x" * 100)

        mock_client = AsyncMock()
        mock_client.audio.transcriptions.create.return_value = MagicMock(
            model_dump=lambda: {
                "text": "Segment one. Segment two.",
                "duration": 12.0,
                "language": "en",
                "segments": [
                    {"id": 0, "start": 0.0, "end": 6.0, "text": " Segment one."},
                    {"id": 1, "start": 6.0, "end": 12.0, "text": " Segment two."},
                ],
            }
        )
        service = TranscriptionService(client=mock_client)
        result = await service.transcribe(audio_file)

        assert len(result["segments"]) == 2
        assert result["segments"][0]["text"] == "Segment one."
        assert result["segments"][1]["start"] == 6.0

    async def test_normalize_response_handles_missing_segments(self) -> None:
        response = MagicMock()
        response.model_dump.return_value = {
            "text": "Plain text only",
            "duration": 3.0,
            "language": "en",
            # No 'segments' key
        }
        result = TranscriptionService._normalize_response(response)
        assert result["segments"] == []
        assert result["text"] == "Plain text only"


# ════════════════════════════════════════════════════════════
# EmbeddingService
# ════════════════════════════════════════════════════════════

@pytest.mark.asyncio
class TestEmbeddingService:
    async def test_embed_texts_single_batch(self) -> None:
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.data = [
            MagicMock(index=0, embedding=[0.1] * 1536),
            MagicMock(index=1, embedding=[0.2] * 1536),
        ]
        mock_client.embeddings.create.return_value = mock_response

        service = EmbeddingService(client=mock_client)
        result = await service.embed_texts(["text one", "text two"])

        assert len(result) == 2
        assert len(result[0]) == 1536
        mock_client.embeddings.create.assert_called_once()

    async def test_embed_texts_empty_input(self) -> None:
        service = EmbeddingService(client=AsyncMock())
        result = await service.embed_texts([])
        assert result == []

    async def test_embed_query_returns_single_vector(self) -> None:
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.data = [MagicMock(index=0, embedding=[0.5] * 1536)]
        mock_client.embeddings.create.return_value = mock_response

        service = EmbeddingService(client=mock_client)
        result = await service.embed_query("What is machine learning?")

        assert len(result) == 1536

    async def test_embed_batch_cleans_newlines(self) -> None:
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.data = [MagicMock(index=0, embedding=[0.1] * 1536)]
        mock_client.embeddings.create.return_value = mock_response

        service = EmbeddingService(client=mock_client)
        await service._embed_batch(["text\nwith\nnewlines"])

        call_args = mock_client.embeddings.create.call_args
        assert "\n" not in call_args.kwargs["input"][0]

    async def test_embed_texts_batches_large_input(self) -> None:
        """Verify batching logic fires for >100 texts."""
        mock_client = AsyncMock()

        def make_response(n):
            resp = MagicMock()
            resp.data = [MagicMock(index=i, embedding=[0.1] * 1536) for i in range(n)]
            return resp

        mock_client.embeddings.create.side_effect = [
            make_response(100),
            make_response(10),
        ]

        service = EmbeddingService(client=mock_client)
        result = await service.embed_texts(["text"] * 110)

        assert len(result) == 110
        assert mock_client.embeddings.create.call_count == 2


# ════════════════════════════════════════════════════════════
# RAG Pipeline helpers
# ════════════════════════════════════════════════════════════

class TestRAGHelpers:
    def test_fmt_time_formats_seconds(self) -> None:
        assert _fmt_time(0) == "00:00"
        assert _fmt_time(65) == "01:05"
        assert _fmt_time(3600) == "60:00"

    def test_chunk_label_with_page(self) -> None:
        chunk = {"page_num": 3, "start_time": None, "end_time": None}
        label = _chunk_label(chunk, 0)
        assert "Page 3" in label

    def test_chunk_label_with_timestamp(self) -> None:
        chunk = {"page_num": None, "start_time": 120.0, "end_time": 150.0}
        label = _chunk_label(chunk, 1)
        assert "02:00" in label
        assert "02:30" in label

    def test_chunk_label_fallback(self) -> None:
        chunk = {"page_num": None, "start_time": None}
        label = _chunk_label(chunk, 2)
        assert "Source 3" in label

    def test_build_citations_truncates_long_content(self) -> None:
        chunks = [
            {
                "id": str(uuid.uuid4()),
                "content": "x" * 500,
                "page_num": 1,
                "start_time": None,
                "end_time": None,
            }
        ]
        citations = _build_citations(chunks)
        assert len(citations[0]["text_snippet"]) <= 210  # 200 + "…"

    def test_build_citations_short_content(self) -> None:
        chunks = [
            {
                "id": str(uuid.uuid4()),
                "content": "Short text.",
                "page_num": None,
                "start_time": 10.0,
                "end_time": 20.0,
            }
        ]
        citations = _build_citations(chunks)
        assert citations[0]["text_snippet"] == "Short text."
        assert citations[0]["start_time"] == 10.0


@pytest.mark.asyncio
class TestRAGPipeline:
    async def test_stream_answer_no_chunks_emits_fallback(self) -> None:
        mock_db = AsyncMock()
        mock_emb = AsyncMock()
        mock_emb.similarity_search.return_value = []

        pipeline = RAGPipeline(db=mock_db, embedding_service=mock_emb)
        events = []
        async for chunk in pipeline.stream_answer("question", uuid.uuid4(), []):
            events.append(chunk)

        import json
        types = [json.loads(e.split("data: ")[1])["type"] for e in events]
        assert "token" in types
        assert "done" in types

    async def test_stream_answer_yields_citations(self) -> None:
        mock_db = AsyncMock()
        mock_emb = AsyncMock()
        chunk_id = str(uuid.uuid4())
        mock_emb.similarity_search.return_value = [
            {
                "id": chunk_id,
                "content": "The answer is in this passage.",
                "chunk_index": 0,
                "page_num": 2,
                "start_time": None,
                "end_time": None,
                "score": 0.9,
            }
        ]

        mock_llm = AsyncMock()

        async def fake_aiter():
            yield "Answer"
            yield " text"

        mock_callback = MagicMock()
        mock_callback.aiter = fake_aiter

        with patch("app.services.rag_pipeline.AsyncIteratorCallbackHandler", return_value=mock_callback):
            with patch("asyncio.create_task"):
                pipeline = RAGPipeline(db=mock_db, embedding_service=mock_emb, llm=mock_llm)
                events = []
                async for e in pipeline.stream_answer("What?", uuid.uuid4(), []):
                    events.append(e)

        import json
        citation_events = [
            json.loads(e.split("data: ")[1])
            for e in events
            if '"citations"' in e
        ]
        assert len(citation_events) == 1
        assert citation_events[0]["data"][0]["chunk_id"] == chunk_id


# ════════════════════════════════════════════════════════════
# SummarizerService
# ════════════════════════════════════════════════════════════

@pytest.mark.asyncio
class TestSummarizerService:
    async def test_returns_cached_summary(self) -> None:
        mock_db = AsyncMock()
        mock_cache = AsyncMock()
        mock_cache.get_summary.return_value = "Cached summary text."

        service = SummarizerService(db=mock_db, cache=mock_cache)
        summary, cached = await service.summarize(uuid.uuid4())

        assert summary == "Cached summary text."
        assert cached is True

    async def test_no_chunks_returns_fallback(self) -> None:
        from unittest.mock import MagicMock
        from sqlalchemy.ext.asyncio import AsyncSession

        mock_cache = AsyncMock()
        mock_cache.get_summary.return_value = None

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db = AsyncMock(spec=AsyncSession)
        mock_db.execute.return_value = mock_result

        service = SummarizerService(db=mock_db, cache=mock_cache)
        summary, cached = await service.summarize(uuid.uuid4())

        assert "No content" in summary
        assert cached is False

    async def test_map_chunk_returns_empty_on_failure(self) -> None:
        import asyncio
        mock_db = AsyncMock()
        mock_cache = AsyncMock()
        mock_llm = AsyncMock()
        mock_llm.ainvoke.side_effect = Exception("OpenAI error")

        service = SummarizerService(db=mock_db, cache=mock_cache, llm=mock_llm)
        sem = asyncio.Semaphore(1)
        result = await service._map_chunk("Some content", sem)
        assert result == ""


# ════════════════════════════════════════════════════════════
# RedisCache
# ════════════════════════════════════════════════════════════

@pytest.mark.asyncio
class TestRedisCache:
    async def test_get_chat_history_returns_empty_when_missing(self) -> None:
        cache = RedisCache()
        cache._client = AsyncMock()
        cache._client.get.return_value = None

        result = await cache.get_chat_history("nonexistent-session")
        assert result == []

    async def test_append_chat_message_limits_to_20(self) -> None:
        cache = RedisCache()
        cache._client = AsyncMock()

        # Simulate 22 existing messages
        existing = [{"role": "user", "content": f"msg {i}"} for i in range(22)]
        import json
        cache._client.get.return_value = json.dumps(existing)

        await cache.append_chat_message("session-1", {"role": "user", "content": "new msg"})

        set_call = cache._client.setex.call_args
        saved = json.loads(set_call.args[2])
        assert len(saved) == 20

    async def test_set_and_get_summary(self) -> None:
        cache = RedisCache()
        cache._client = AsyncMock()
        import json
        cache._client.get.return_value = json.dumps("Test summary text")

        result = await cache.get_summary("doc-123")
        assert result == "Test summary text"

    async def test_client_raises_when_not_connected(self) -> None:
        cache = RedisCache()
        with pytest.raises(RuntimeError, match="not connected"):
            _ = cache.client
