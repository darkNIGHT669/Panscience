"""
conftest.py
───────────
Shared test fixtures using dependency injection override pattern.
No real OpenAI/Whisper calls are made — all external services are mocked.
"""

import asyncio
import uuid
from typing import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.core.security import create_access_token, hash_password
from app.db.models import *  # noqa — register models
from app.db.session import Base
from app.main import app
from app.api.deps import get_db, get_redis, get_current_user
from app.db.models.user import User

# ─── Test Database (SQLite in-memory) ─────────────────────────────────────────
# We use SQLite for speed; pgvector-specific queries are tested via integration tests.

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"

test_engine = create_async_engine(
    TEST_DB_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

TestSessionLocal = async_sessionmaker(
    bind=test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="function")
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    async with test_engine.begin() as conn:
        # Drop vector extension calls for SQLite compatibility
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    async with TestSessionLocal() as session:
        yield session
        await session.rollback()


# ─── Mock Services ────────────────────────────────────────────────────────────

@pytest.fixture
def mock_embedding_service():
    service = AsyncMock()
    service.embed_texts.return_value = [[0.1] * 1536]
    service.embed_query.return_value = [0.1] * 1536
    service.similarity_search.return_value = [
        {
            "id": str(uuid.uuid4()),
            "content": "This is a test chunk about machine learning.",
            "chunk_index": 0,
            "page_num": 1,
            "start_time": None,
            "end_time": None,
            "score": 0.92,
        }
    ]
    service.similarity_search_by_topic.return_value = [
        {
            "id": str(uuid.uuid4()),
            "content": "Discussion of neural networks starts here.",
            "start_time": 120.5,
            "end_time": 150.3,
            "score": 0.88,
        }
    ]
    return service


@pytest.fixture
def mock_transcription_service():
    service = AsyncMock()
    service.transcribe.return_value = {
        "text": "Hello world. This is a test transcription.",
        "segments": [
            {"id": 0, "start": 0.0, "end": 5.0, "text": "Hello world."},
            {"id": 1, "start": 5.0, "end": 10.0, "text": "This is a test transcription."},
        ],
        "duration": 10.0,
        "language": "en",
    }
    return service


@pytest.fixture
def mock_redis():
    cache = AsyncMock()
    cache.get_chat_history.return_value = []
    cache.append_chat_message.return_value = None
    cache.get_summary.return_value = None
    cache.set_summary.return_value = None
    cache.clear_chat_history.return_value = None
    return cache


@pytest.fixture
def mock_rag_pipeline():
    async def fake_stream(*args, **kwargs):
        import json
        yield f"data: {json.dumps({'type': 'token', 'data': 'The '})}\n\n"
        yield f"data: {json.dumps({'type': 'token', 'data': 'answer is 42.'})}\n\n"
        yield f"data: {json.dumps({'type': 'citations', 'data': []})}\n\n"
        yield f"data: {json.dumps({'type': 'done', 'data': None})}\n\n"

    pipeline = MagicMock()
    pipeline.stream_answer = fake_stream
    return pipeline


# ─── Test User & Auth ─────────────────────────────────────────────────────────

@pytest_asyncio.fixture
async def test_user(db_session: AsyncSession) -> User:
    user = User(
        email="test@panscience.ai",
        hashed_password=hash_password("TestPass123!"),
        full_name="Test User",
    )
    db_session.add(user)
    await db_session.flush()
    return user


@pytest.fixture
def auth_token(test_user: User) -> str:
    return create_access_token(subject=str(test_user.id))


@pytest.fixture
def auth_headers(auth_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {auth_token}"}


# ─── HTTP Client ──────────────────────────────────────────────────────────────

@pytest_asyncio.fixture
async def client(
    db_session: AsyncSession,
    mock_redis,
    test_user: User,
) -> AsyncGenerator[AsyncClient, None]:
    """HTTP test client with DB and Redis overridden."""

    async def override_db():
        yield db_session

    async def override_redis():
        return mock_redis

    async def override_current_user():
        return test_user

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_redis] = override_redis
    app.dependency_overrides[get_current_user] = override_current_user

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def unauthed_client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """HTTP test client without auth override — for testing 401 responses."""

    async def override_db():
        yield db_session

    app.dependency_overrides[get_db] = override_db

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac

    app.dependency_overrides.clear()
