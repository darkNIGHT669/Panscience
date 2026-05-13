import json
from typing import Any

import redis.asyncio as aioredis

from app.core.config import get_settings
from app.core.logging import get_logger

settings = get_settings()
logger = get_logger(__name__)

CHAT_HISTORY_PREFIX = "chat_history:"
SUMMARY_PREFIX = "summary:"
RATE_LIMIT_PREFIX = "rate_limit:"


class RedisCache:
    def __init__(self) -> None:
        self._client: aioredis.Redis | None = None

    async def connect(self) -> None:
        self._client = aioredis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
        )
        await self._client.ping()
        logger.info("Redis connected successfully")

    async def disconnect(self) -> None:
        if self._client:
            await self._client.aclose()

    @property
    def client(self) -> aioredis.Redis:
        if not self._client:
            raise RuntimeError("Redis not connected. Call connect() first.")
        return self._client

    # ─── Generic ──────────────────────────────────────────────────────────────

    async def get(self, key: str) -> Any | None:
        value = await self.client.get(key)
        if value is None:
            return None
        try:
            return json.loads(value)
        except (json.JSONDecodeError, TypeError):
            return value

    async def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        serialized = json.dumps(value) if not isinstance(value, str) else value
        if ttl:
            await self.client.setex(key, ttl, serialized)
        else:
            await self.client.set(key, serialized)

    async def delete(self, key: str) -> None:
        await self.client.delete(key)

    async def exists(self, key: str) -> bool:
        return bool(await self.client.exists(key))

    # ─── Chat History ─────────────────────────────────────────────────────────

    async def get_chat_history(self, session_id: str) -> list[dict]:
        key = f"{CHAT_HISTORY_PREFIX}{session_id}"
        data = await self.get(key)
        return data if isinstance(data, list) else []

    async def append_chat_message(self, session_id: str, message: dict) -> None:
        key = f"{CHAT_HISTORY_PREFIX}{session_id}"
        history = await self.get_chat_history(session_id)
        history.append(message)
        # Keep last 20 messages to manage context window
        history = history[-20:]
        await self.set(key, history, ttl=settings.CHAT_HISTORY_TTL)

    async def clear_chat_history(self, session_id: str) -> None:
        await self.delete(f"{CHAT_HISTORY_PREFIX}{session_id}")

    # ─── Summary Cache ────────────────────────────────────────────────────────

    async def get_summary(self, document_id: str) -> str | None:
        return await self.get(f"{SUMMARY_PREFIX}{document_id}")

    async def set_summary(self, document_id: str, summary: str) -> None:
        # Summaries are stable; cache for 24 hours
        await self.set(f"{SUMMARY_PREFIX}{document_id}", summary, ttl=86400)
