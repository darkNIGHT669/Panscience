from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache
from typing import Literal


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # App
    APP_NAME: str = "PanScience Q&A"
    APP_VERSION: str = "1.0.0"
    ENVIRONMENT: Literal["development", "testing", "production"] = "development"
    DEBUG: bool = True

    # API
    API_PREFIX: str = "/api"
    CORS_ORIGINS: list[str] = ["http://localhost:3000", "http://frontend:3000"]

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://panscience:panscience@localhost:5432/panscience"
    DATABASE_URL_SYNC: str = "postgresql://panscience:panscience@localhost:5432/panscience"

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"
    CHAT_HISTORY_TTL: int = 3600  # 1 hour in seconds
    RATE_LIMIT_PER_MINUTE: int = 20

    # Auth / JWT
    SECRET_KEY: str = "super-secret-change-in-production-please-use-32-chars"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 hours

    # OpenAI
    OPENAI_API_KEY: str
    OPENAI_CHAT_MODEL: str = "gpt-4o"
    OPENAI_EMBEDDING_MODEL: str = "text-embedding-3-small"
    OPENAI_EMBEDDING_DIMENSIONS: int = 1536
    WHISPER_MODEL: str = "whisper-1"

    # File Storage
    UPLOAD_DIR: str = "/app/uploads"
    MAX_FILE_SIZE_MB: int = 500
    ALLOWED_AUDIO_TYPES: list[str] = ["audio/mpeg", "audio/wav", "audio/mp4", "audio/ogg", "audio/webm"]
    ALLOWED_VIDEO_TYPES: list[str] = ["video/mp4", "video/webm", "video/ogg", "video/quicktime"]
    ALLOWED_PDF_TYPES: list[str] = ["application/pdf"]

    # RAG
    CHUNK_SIZE: int = 800          # tokens per chunk
    CHUNK_OVERLAP: int = 150       # overlap between chunks
    TOP_K_RETRIEVAL: int = 5       # chunks returned per query
    AUDIO_CHUNK_SECONDS: int = 30  # seconds per audio/video chunk

    @property
    def max_file_size_bytes(self) -> int:
        return self.MAX_FILE_SIZE_MB * 1024 * 1024


@lru_cache()
def get_settings() -> Settings:
    return Settings()
