# PanScience Q&A — AI-Powered Document & Multimedia Intelligence

> Ask questions about your PDFs, audio, and video files with precise AI-powered citations and timestamp navigation.

[![CI/CD](https://github.com/your-org/panscience-qa/actions/workflows/ci.yml/badge.svg)](https://github.com/your-org/panscience-qa/actions)
[![Coverage](https://codecov.io/gh/your-org/panscience-qa/branch/main/graph/badge.svg)](https://codecov.io/gh/your-org/panscience-qa)

---

## ✨ Features

| Capability | Detail |
|---|---|
| 📄 **PDF Q&A** | Upload any PDF; ask questions with page-level citations |
| 🎵 **Audio Q&A** | MP3/WAV/M4A transcription + semantic search with play buttons |
| 🎬 **Video Q&A** | MP4/MOV/WEBM; jump to exact timestamp from chat |
| 🔍 **Vector Search** | pgvector cosine similarity for semantic retrieval |
| ⚡ **Streaming Answers** | Token-by-token GPT-4o responses via SSE |
| 📊 **Smart Summaries** | Map-reduce summarization (cached in Redis) |
| 🔒 **JWT Auth** | Secure multi-user sessions |
| 🚦 **Rate Limiting** | 20 chat requests/minute per user (Redis-backed) |

---

## 🏗️ Architecture

```
┌────────────────────────────────────────────────────────────────┐
│                         Nginx (port 80)                         │
│              /api/* → FastAPI    /  → Next.js                  │
└────────────────┬───────────────────────────┬───────────────────┘
                 │                           │
    ┌────────────▼──────────┐   ┌────────────▼──────────┐
    │   FastAPI Backend     │   │   Next.js Frontend    │
    │   (Python 3.12)       │   │   (React 18, App Router)│
    │                       │   │                        │
    │ • LangChain RAG       │   │ • Zustand state        │
    │ • Whisper API         │   │ • SSE streaming        │
    │ • pgvector search     │   │ • react-player seek    │
    │ • SSE streaming       │   │ • TanStack Query       │
    └────────┬──────────────┘   └────────────────────────┘
             │
    ┌────────▼──────────────────────────────┐
    │        PostgreSQL + pgvector           │
    │   users · documents · chunks(1536d)   │
    │   chat_sessions · messages            │
    └───────────────────────────────────────┘
             │
    ┌────────▼──────────┐
    │       Redis        │
    │  chat history TTL  │
    │  summary cache     │
    │  rate limiter      │
    └────────────────────┘
```

### Key Architecture Decisions

**1. Timestamp Strategy**
Whisper API is called with `response_format="verbose_json"` and `timestamp_granularities=["segment"]`. This returns word-level start/end times per segment. During ingestion, segments are grouped into ~30-second chunks and stored with `start_time` / `end_time` in the database. When the RAG pipeline retrieves a chunk, its timestamps are returned as citations. The frontend `react-player` calls `.seekTo(start_time, "seconds")` via a Zustand store event — fully decoupled from the chat component.

**2. RAG Pipeline**
Uses LangChain's `ChatOpenAI` with `AsyncIteratorCallbackHandler` for non-blocking streaming. Tokens are piped directly into an SSE `StreamingResponse`. The retriever is pgvector (`<=>` cosine operator with an IVFFlat index), keeping everything in a single Postgres instance.

**3. 95% Test Coverage**
Every FastAPI route uses `Depends()` for service injection. Tests override all dependencies via `app.dependency_overrides` — no real OpenAI, Whisper, or Redis calls. `AsyncMock` replaces all I/O. The SQLite in-memory database replaces Postgres for unit tests; integration tests use a real Postgres service in CI.

**4. Large File Handling**
Files >24 MB are split into 10-minute MP3 segments via `ffmpeg` before being sent to Whisper (25 MB API limit). Timestamps are offset-corrected and merged before chunking.

**5. Redis Double Duty**
- Chat history: last 20 messages per session, 1-hour TTL (avoids DB reads on every token)
- Summary cache: 24-hour TTL (map-reduce is expensive)
- Rate limiting: `SlowAPI` uses Redis for distributed rate limiting (20 chat requests/minute/user)

---

## 🚀 Quick Start

### Prerequisites
- Docker & Docker Compose
- An OpenAI API key

### 1. Clone & Configure
```bash
git clone https://github.com/your-org/panscience-qa.git
cd panscience-qa
cp .env.example .env
# Edit .env and add your OPENAI_API_KEY
```

### 2. Start All Services
```bash
docker compose up --build
```

The first run will:
1. Pull/build all images (~3–5 minutes)
2. Run Alembic migrations
3. Start Nginx, FastAPI, Next.js, Postgres, Redis

### 3. Access the Application
| Service | URL |
|---|---|
| **Web App** | http://localhost |
| **API Docs** | http://localhost/api/docs |
| **ReDoc** | http://localhost/api/redoc |

### 4. Create an Account
Go to http://localhost, click "Create one free", register, then sign in.

---

## 🧪 Running Tests

### Backend (95% coverage enforced)
```bash
cd backend
pip install -r requirements.txt
pip install aiosqlite
pytest --cov=app --cov-report=term-missing
```

### Frontend
```bash
cd frontend
npm install
npm test -- --coverage
```

### Full stack via Docker
```bash
docker compose -f docker-compose.test.yml up --abort-on-container-exit
```

---

## 📡 API Reference

All endpoints require `Authorization: Bearer <token>` except `/api/auth/register` and `/api/auth/login`.

### Auth

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/auth/register` | Create account |
| `POST` | `/api/auth/login` | Get JWT token |
| `GET` | `/api/auth/me` | Current user info |

**Login response:**
```json
{ "access_token": "eyJ...", "token_type": "bearer" }
```

### Documents

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/documents/upload` | Upload PDF/audio/video (multipart) |
| `GET` | `/api/documents/` | List user's documents |
| `GET` | `/api/documents/{id}` | Get document metadata |
| `DELETE` | `/api/documents/{id}` | Delete document + chunks |
| `GET` | `/api/documents/{id}/summary` | Get AI summary |
| `GET` | `/api/documents/{id}/timestamps?topic=X` | Find timestamps for a topic |

**Upload example:**
```bash
curl -X POST http://localhost/api/documents/upload \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@report.pdf"
```

**Document status lifecycle:** `processing` → `ready` | `error`

### Chat

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/chat/sessions` | Create chat session |
| `GET` | `/api/chat/sessions` | List sessions |
| `DELETE` | `/api/chat/sessions/{id}` | Delete session |
| `GET` | `/api/chat/sessions/{id}/messages` | Message history |
| `POST` | `/api/chat/sessions/{id}/messages` | **Send question (SSE stream)** |

**Streaming chat example:**
```bash
curl -N -X POST http://localhost/api/chat/sessions/$SESSION_ID/messages \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"question": "What are the key findings?"}' \
  --no-buffer
```

**SSE Event types:**
```
data: {"type": "token",     "data": "The "}
data: {"type": "token",     "data": "findings show…"}
data: {"type": "citations", "data": [{"chunk_id":"…","start_time":120.5,"page_num":null,"text_snippet":"…"}]}
data: {"type": "done",      "data": null}
data: {"type": "error",     "data": "Something went wrong"}
```

---

## 🗂️ Project Structure

```
panscience-qa/
├── backend/
│   ├── app/
│   │   ├── api/routes/     # auth, upload, chat
│   │   ├── core/           # config, security, logging
│   │   ├── db/models/      # user, document, chunk, chat
│   │   ├── services/       # file_processor, transcription, embeddings, rag, summarizer, cache
│   │   └── schemas/        # Pydantic request/response models
│   └── tests/              # 95%+ coverage
├── frontend/
│   ├── src/
│   │   ├── app/            # Next.js App Router pages
│   │   ├── components/     # FileUploader, FileList, ChatWindow, MessageBubble, MediaPlayer, SummaryPanel
│   │   ├── hooks/          # useChat, useUpload, useMediaPlayer
│   │   ├── lib/            # api client, types, utils
│   │   └── store/          # Zustand global state
│   └── __tests__/          # Jest + RTL
├── nginx/nginx.conf
├── docker-compose.yml
└── .github/workflows/ci.yml
```

---

## 🔧 Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `OPENAI_API_KEY` | ✅ | — | OpenAI API key |
| `SECRET_KEY` | ✅ | — | JWT signing secret (32+ chars) |
| `DATABASE_URL` | — | Postgres in compose | Async SQLAlchemy URL |
| `REDIS_URL` | — | Redis in compose | Redis connection URL |
| `OPENAI_CHAT_MODEL` | — | `gpt-4o` | Chat model |
| `MAX_FILE_SIZE_MB` | — | `500` | Upload size limit |
| `RATE_LIMIT_PER_MINUTE` | — | `20` | Chat rate limit per user |
| `AUDIO_CHUNK_SECONDS` | — | `30` | Seconds per audio chunk |
| `TOP_K_RETRIEVAL` | — | `5` | Chunks retrieved per query |

---

## 📹 Walkthrough Video Script

For your demo, cover these sections in order:

1. **Architecture overview** (2 min) — Show the `docker-compose.yml` and diagram
2. **Upload a PDF** (2 min) — Drag a research paper; show processing status polling
3. **PDF Q&A + citations** (3 min) — Ask a question; show page citations expanding
4. **Upload audio/video** (2 min) — Upload a lecture recording; wait for transcription
5. **Timestamp navigation** (3 min) — Ask "where does the speaker discuss methodology?"; click play button to jump
6. **Summary feature** (1 min) — Click AI Summary panel; show map-reduce in action
7. **Streaming demo** (1 min) — Show token-by-token streaming in network DevTools
8. **Test coverage** (1 min) — Run `pytest --cov` live in terminal showing 95%+

---

## 📄 License

MIT © PanScience Innovations
