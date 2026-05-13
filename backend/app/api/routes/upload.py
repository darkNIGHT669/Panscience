import uuid

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.core.config import get_settings
from app.db.models.document import Document
from app.db.models.user import User
from app.schemas import DocumentListOut, DocumentOut
from app.services.embeddings import EmbeddingService
from app.services.file_processor import FileProcessorService
from app.services.transcription import TranscriptionService

settings = get_settings()
router = APIRouter(prefix="/documents", tags=["documents"])

ALLOWED_MIME_TYPES = (
    settings.ALLOWED_PDF_TYPES
    + settings.ALLOWED_AUDIO_TYPES
    + settings.ALLOWED_VIDEO_TYPES
)


@router.post("/upload", response_model=DocumentOut, status_code=status.HTTP_202_ACCEPTED)
async def upload_document(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Document:
    # Validate MIME type
    if file.content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"File type '{file.content_type}' is not supported. "
                   f"Allowed: PDF, MP3, MP4, WAV, OGG, WEBM, MOV.",
        )

    processor = FileProcessorService(
        db=db,
        embedding_service=EmbeddingService(),
        transcription_service=TranscriptionService(),
    )
    document = await processor.ingest(upload_file=file, user_id=current_user.id)
    return document


@router.get("/", response_model=DocumentListOut)
async def list_documents(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    result = await db.execute(
        select(Document)
        .where(Document.user_id == current_user.id)
        .order_by(Document.created_at.desc())
    )
    documents = result.scalars().all()
    return {"documents": documents, "total": len(documents)}


@router.get("/{document_id}", response_model=DocumentOut)
async def get_document(
    document_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Document:
    return await _get_owned_document(db, document_id, current_user.id)


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    document_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    document = await _get_owned_document(db, document_id, current_user.id)
    await db.delete(document)


# ─── Summary (delegated to summarizer service) ────────────────────────────────

@router.get("/{document_id}/summary")
async def get_summary(
    document_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    from app.api.deps import get_redis
    from app.services.summarizer import SummarizerService

    document = await _get_owned_document(db, document_id, current_user.id)
    _assert_ready(document)

    # Use cached summary if already computed
    if document.summary:
        return {"document_id": str(document_id), "summary": document.summary, "cached": True}

    cache = await get_redis()
    summarizer = SummarizerService(db=db, cache=cache)
    summary, cached = await summarizer.summarize(document_id)
    return {"document_id": str(document_id), "summary": summary, "cached": cached}


# ─── Timestamps ───────────────────────────────────────────────────────────────

@router.get("/{document_id}/timestamps")
async def get_timestamps(
    document_id: uuid.UUID,
    topic: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    document = await _get_owned_document(db, document_id, current_user.id)
    _assert_ready(document)

    if document.file_type not in ("audio", "video"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Timestamp search is only available for audio and video documents.",
        )

    embedding_service = EmbeddingService()
    results = await embedding_service.similarity_search_by_topic(
        db=db,
        topic=topic,
        document_id=document_id,
        top_k=10,
    )

    return {
        "document_id": str(document_id),
        "topic": topic,
        "results": [
            {
                "chunk_id": r["id"],
                "start_time": r["start_time"],
                "end_time": r["end_time"],
                "text": r["content"],
                "relevance_score": r["score"],
            }
            for r in results
        ],
    }


# ─── Helpers ──────────────────────────────────────────────────────────────────

async def _get_owned_document(
    db: AsyncSession, document_id: uuid.UUID, user_id: uuid.UUID
) -> Document:
    result = await db.execute(
        select(Document).where(
            Document.id == document_id,
            Document.user_id == user_id,
        )
    )
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")
    return doc


def _assert_ready(document: Document) -> None:
    if document.status != "ready":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Document is not ready yet (status: {document.status}). Please wait.",
        )
