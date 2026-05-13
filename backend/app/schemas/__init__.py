from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, EmailStr, Field, field_validator


# ─────────────────────── Auth ───────────────────────

class UserRegister(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    full_name: str | None = Field(default=None, max_length=255)


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    id: uuid.UUID
    email: str
    full_name: str | None
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


# ─────────────────────── Documents ───────────────────────

class DocumentOut(BaseModel):
    id: uuid.UUID
    filename: str
    original_filename: str
    file_type: str
    mime_type: str
    file_size_bytes: int
    status: str
    error_message: str | None
    summary: str | None
    duration_seconds: float | None
    page_count: int | None
    created_at: datetime

    model_config = {"from_attributes": True}


class DocumentListOut(BaseModel):
    documents: list[DocumentOut]
    total: int


# ─────────────────────── Chunks / Timestamps ───────────────────────

class TimestampEntry(BaseModel):
    chunk_id: uuid.UUID
    start_time: float
    end_time: float
    text: str
    relevance_score: float | None = None


class TimestampResponse(BaseModel):
    document_id: uuid.UUID
    topic: str
    results: list[TimestampEntry]


# ─────────────────────── Chat ───────────────────────

class ChatSessionCreate(BaseModel):
    document_id: uuid.UUID
    title: str | None = None


class ChatSessionOut(BaseModel):
    id: uuid.UUID
    document_id: uuid.UUID | None
    title: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class Citation(BaseModel):
    chunk_id: uuid.UUID
    page_num: int | None = None
    start_time: float | None = None
    end_time: float | None = None
    text_snippet: str


class MessageOut(BaseModel):
    id: uuid.UUID
    session_id: uuid.UUID
    role: str
    content: str
    citations: list[Citation] | None
    created_at: datetime

    model_config = {"from_attributes": True}

    @field_validator("citations", mode="before")
    @classmethod
    def parse_citations(cls, v: Any) -> list[Citation] | None:
        if v is None:
            return None
        if isinstance(v, list):
            return [Citation(**item) if isinstance(item, dict) else item for item in v]
        return v


class ChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=4000)


class StreamChunk(BaseModel):
    """Server-Sent Event payload for streaming chat tokens."""
    type: str  # "token" | "citations" | "done" | "error"
    data: str | list[dict] | None = None


# ─────────────────────── Summary ───────────────────────

class SummaryResponse(BaseModel):
    document_id: uuid.UUID
    summary: str
    cached: bool = False


# ─────────────────────── Health ───────────────────────

class HealthResponse(BaseModel):
    status: str
    version: str
    environment: str
