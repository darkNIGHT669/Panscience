"""
file_processor.py
─────────────────
Orchestrates the full ingestion pipeline:
  1. Validate MIME type & size
  2. Save file to disk
  3. Extract text (PDF) or transcribe (audio/video via Whisper API)
  4. Chunk the text, preserving timestamps or page numbers
  5. Generate embeddings and persist chunks to DB
  6. Update document status
"""

import asyncio
import os
import uuid
from pathlib import Path

import aiofiles
import fitz  # PyMuPDF
from fastapi import UploadFile
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.logging import get_logger
from app.db.models.document import Chunk, Document
from app.services.embeddings import EmbeddingService
from app.services.transcription import TranscriptionService

settings = get_settings()
logger = get_logger(__name__)


class FileProcessorService:
    def __init__(
        self,
        db: AsyncSession,
        embedding_service: EmbeddingService,
        transcription_service: TranscriptionService,
    ) -> None:
        self.db = db
        self.embedding_service = embedding_service
        self.transcription_service = transcription_service

    # ─── Public Entry Point ───────────────────────────────────────────────────

    async def ingest(self, upload_file: UploadFile, user_id: uuid.UUID) -> Document:
        """Validate, save, and start async processing of an uploaded file."""
        mime_type = upload_file.content_type or "application/octet-stream"
        file_type = self._resolve_file_type(mime_type)

        # Create DB record immediately so the user sees the document
        document = Document(
            user_id=user_id,
            filename=self._safe_filename(upload_file.filename or "upload"),
            original_filename=upload_file.filename or "upload",
            file_type=file_type,
            mime_type=mime_type,
            storage_path="",       # filled after save
            file_size_bytes=0,     # filled after save
            status="processing",
        )
        self.db.add(document)
        await self.db.flush()      # get the UUID without committing

        try:
            storage_path, file_size = await self._save_to_disk(upload_file, document.id)
            document.storage_path = str(storage_path)
            document.file_size_bytes = file_size
            await self.db.flush()

            # Run heavy processing in a background task (non-blocking for the response)
            asyncio.create_task(self._process_document(document.id, storage_path, file_type))

        except Exception as exc:
            logger.exception("Failed to save uploaded file: %s", exc)
            document.status = "error"
            document.error_message = str(exc)

        return document

    # ─── Disk I/O ─────────────────────────────────────────────────────────────

    async def _save_to_disk(self, upload_file: UploadFile, doc_id: uuid.UUID) -> tuple[Path, int]:
        upload_dir = Path(settings.UPLOAD_DIR) / str(doc_id)
        upload_dir.mkdir(parents=True, exist_ok=True)

        safe_name = self._safe_filename(upload_file.filename or "upload")
        dest = upload_dir / safe_name
        total_bytes = 0

        async with aiofiles.open(dest, "wb") as f:
            while chunk := await upload_file.read(1024 * 1024):  # 1 MB chunks
                if total_bytes + len(chunk) > settings.max_file_size_bytes:
                    await f.close()
                    dest.unlink(missing_ok=True)
                    raise ValueError(
                        f"File exceeds maximum size of {settings.MAX_FILE_SIZE_MB} MB"
                    )
                await f.write(chunk)
                total_bytes += len(chunk)

        logger.info("Saved %s bytes to %s", total_bytes, dest)
        return dest, total_bytes

    # ─── Processing Orchestration ─────────────────────────────────────────────

    async def _process_document(
        self, doc_id: uuid.UUID, storage_path: Path, file_type: str
    ) -> None:
        """Full ingestion pipeline — runs as a background asyncio task."""
        from app.db.session import AsyncSessionLocal  # local import to get a fresh session

        async with AsyncSessionLocal() as session:
            try:
                if file_type == "pdf":
                    chunks_data = await self._process_pdf(storage_path)
                else:
                    chunks_data, duration = await self._process_media(storage_path)
                    await session.execute(
                        update(Document)
                        .where(Document.id == doc_id)
                        .values(duration_seconds=duration)
                    )

                await self._store_chunks(session, doc_id, chunks_data)

                await session.execute(
                    update(Document)
                    .where(Document.id == doc_id)
                    .values(status="ready")
                )
                await session.commit()
                logger.info("Document %s ingestion complete (%d chunks)", doc_id, len(chunks_data))

            except Exception as exc:
                logger.exception("Document %s ingestion failed: %s", doc_id, exc)
                await session.rollback()
                await session.execute(
                    update(Document)
                    .where(Document.id == doc_id)
                    .values(status="error", error_message=str(exc)[:1000])
                )
                await session.commit()

    # ─── PDF Processing ───────────────────────────────────────────────────────

    async def _process_pdf(self, path: Path) -> list[dict]:
        """Extract text from PDF, split into overlapping chunks keyed by page number."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._extract_pdf_chunks, path)

    def _extract_pdf_chunks(self, path: Path) -> list[dict]:
        chunks = []
        doc = fitz.open(str(path))
        buffer = ""
        buffer_pages: list[int] = []
        chunk_index = 0

        for page_num, page in enumerate(doc, start=1):
            page_text = page.get_text("text").strip()
            if not page_text:
                continue
            buffer += f"\n{page_text}"
            buffer_pages.append(page_num)

            # Flush when buffer exceeds chunk size (approx token count ≈ chars/4)
            while len(buffer) // 4 >= settings.CHUNK_SIZE:
                split_at = settings.CHUNK_SIZE * 4
                chunk_text = buffer[:split_at].strip()
                overlap_text = buffer[split_at - settings.CHUNK_OVERLAP * 4:]

                if chunk_text:
                    chunks.append({
                        "content": chunk_text,
                        "chunk_index": chunk_index,
                        "page_num": buffer_pages[0] if buffer_pages else page_num,
                        "start_time": None,
                        "end_time": None,
                    })
                    chunk_index += 1

                buffer = overlap_text
                buffer_pages = [page_num]

        # Flush remainder
        if buffer.strip():
            chunks.append({
                "content": buffer.strip(),
                "chunk_index": chunk_index,
                "page_num": buffer_pages[0] if buffer_pages else 1,
                "start_time": None,
                "end_time": None,
            })

        doc.close()
        return chunks

    # ─── Audio / Video Processing ─────────────────────────────────────────────

    async def _process_media(self, path: Path) -> tuple[list[dict], float]:
        """Transcribe audio/video via Whisper API, split transcript into timed chunks."""
        transcript = await self.transcription_service.transcribe(path)
        segments = transcript.get("segments", [])
        duration = transcript.get("duration", 0.0)

        chunks = []
        chunk_index = 0
        window: list[dict] = []
        window_start = 0.0

        for seg in segments:
            window.append(seg)
            window_duration = (seg.get("end", 0) or 0) - window_start

            if window_duration >= settings.AUDIO_CHUNK_SECONDS:
                chunk_text = " ".join(s["text"].strip() for s in window)
                start_t = window[0].get("start", 0.0)
                end_t = window[-1].get("end", start_t + window_duration)

                chunks.append({
                    "content": chunk_text,
                    "chunk_index": chunk_index,
                    "page_num": None,
                    "start_time": start_t,
                    "end_time": end_t,
                })
                chunk_index += 1

                # Overlap: keep last ~5 seconds of segments
                overlap_start = end_t - 5.0
                window = [s for s in window if (s.get("end") or 0) > overlap_start]
                window_start = window[0].get("start", end_t) if window else end_t

        # Flush remaining
        if window:
            chunk_text = " ".join(s["text"].strip() for s in window)
            chunks.append({
                "content": chunk_text,
                "chunk_index": chunk_index,
                "page_num": None,
                "start_time": window[0].get("start", 0.0),
                "end_time": window[-1].get("end", duration),
            })

        return chunks, duration

    # ─── Embedding & Storage ──────────────────────────────────────────────────

    async def _store_chunks(
        self, session: AsyncSession, doc_id: uuid.UUID, chunks_data: list[dict]
    ) -> None:
        """Batch-embed and insert all chunks."""
        texts = [c["content"] for c in chunks_data]
        embeddings = await self.embedding_service.embed_texts(texts)

        orm_chunks = [
            Chunk(
                document_id=doc_id,
                content=data["content"],
                chunk_index=data["chunk_index"],
                page_num=data.get("page_num"),
                start_time=data.get("start_time"),
                end_time=data.get("end_time"),
                embedding=emb,
            )
            for data, emb in zip(chunks_data, embeddings)
        ]
        session.add_all(orm_chunks)

    # ─── Helpers ──────────────────────────────────────────────────────────────

    def _resolve_file_type(self, mime_type: str) -> str:
        if mime_type in settings.ALLOWED_PDF_TYPES:
            return "pdf"
        if mime_type in settings.ALLOWED_AUDIO_TYPES:
            return "audio"
        if mime_type in settings.ALLOWED_VIDEO_TYPES:
            return "video"
        raise ValueError(f"Unsupported file type: {mime_type}")

    @staticmethod
    def _safe_filename(filename: str) -> str:
        keep = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_.")
        stem = Path(filename).stem
        suffix = Path(filename).suffix
        safe_stem = "".join(c if c in keep else "_" for c in stem)
        return f"{safe_stem[:100]}{suffix}"
