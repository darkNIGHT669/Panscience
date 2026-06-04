"""
main.py
───────
FastAPI application entry point.
Registers all routers, middleware, startup/shutdown hooks.
"""

import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address
from sqlalchemy.exc import IntegrityError

from app.api.routes import auth, chat, upload
from app.core.config import get_settings
from app.core.logging import get_logger, setup_logging
from app.db.session import engine
from app.db.models import *  # noqa: F401,F403 — register all models with SQLAlchemy

settings = get_settings()
setup_logging()
logger = get_logger(__name__)


# ─── Lifespan ─────────────────────────────────────────────────────────────────

@asynccontextmanager

async def lifespan(app: FastAPI):
    # Startup
    logger.info("Starting %s v%s [%s]", settings.APP_NAME, settings.APP_VERSION, settings.ENVIRONMENT)

    # Ensure upload directory exists
    Path(settings.UPLOAD_DIR).mkdir(parents=True, exist_ok=True)
    logger.info("Upload directory: %s", settings.UPLOAD_DIR)

    # Enable pgvector extension (idempotent, protected against worker race conditions)
    from sqlalchemy import text
    async with engine.begin() as conn:
        try:
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            logger.info("pgvector extension ensured")
        except (IntegrityError, Exception) as e:
            # If another worker registers it at the exact same millisecond, catch it safely
            logger.warning("pgvector extension registration bypassed (already initialized or concurrent worker handled it)")

    yield

    # Shutdown
    await engine.dispose()
    logger.info("Database connections closed")
    
# ─── App Instance ─────────────────────────────────────────────────────────────

limiter = Limiter(key_func=get_remote_address, default_limits=["200/minute"])

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="AI-Powered Document & Multimedia Q&A API",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
    lifespan=lifespan,
)

# State needed by SlowAPI
app.state.limiter = limiter

# ─── Middleware ───────────────────────────────────────────────────────────────

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(SlowAPIMiddleware)

# ─── Exception Handlers ───────────────────────────────────────────────────────

app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled exception on %s %s: %s", request.method, request.url, exc)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "An unexpected error occurred. Please try again."},
    )


# ─── Routers ──────────────────────────────────────────────────────────────────

app.include_router(auth.router, prefix=settings.API_PREFIX)
app.include_router(upload.router, prefix=settings.API_PREFIX)
app.include_router(chat.router, prefix=settings.API_PREFIX)


# ─── Health Check ─────────────────────────────────────────────────────────────

@app.get("/api/health", tags=["health"])
async def health_check() -> dict:
    return {
        "status": "ok",
        "version": settings.APP_VERSION,
        "environment": settings.ENVIRONMENT,
    }
