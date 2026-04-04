# Synth - Project Context

## What This Is

AI meeting bot that joins Zoom/Teams/Google Meet as a voice participant. Listens to the meeting, answers questions when invoked ("Hey Assistant"), reads uploaded documents, searches the web, and delivers post-meeting summaries.

## Tech Stack

| Layer | Technology | Notes |
|---|---|---|
| Backend | Python 3.12, FastAPI, SQLAlchemy (async), PostgreSQL | `backend/app/` |
| Frontend | Next.js 16.2.2 (App Router), React 19, Tailwind v4, shadcn/ui | `frontend/` |
| LLM | Gemini 2.5 Flash Lite (primary), Claude Haiku 4.5 (fallback) | Gemini for fast Q&A, Claude for summaries |
| Transcription | Deepgram Nova-3 via Recall.ai (streaming) | Keyword boost for "Hey Assistant" |
| TTS | Kokoro (am_michael voice, 24kHz, 1.1x speed) | Pre-loaded at startup |
| VAD | Silero (per-session instances) | Only used in direct audio path |
| Search | Serper (primary), SearXNG (fallback) | Serper for speed |
| Vector DB | ChromaDB (BAAI/bge-large-en-v1.5 embeddings) | Per-agent collections |
| Meeting Infra | Recall.ai API | Bot deployment + audio + webhooks |

## Running Locally

```bash
# Backend (requires PostgreSQL running on localhost:5432)
cd backend
source .venv/bin/activate
TOKENIZERS_PARALLELISM=false uvicorn app.main:app --reload --port 8000

# Frontend
cd frontend
npm run dev

# Ngrok (for Recall.ai webhooks)
ngrok http 8000
# Update WEBHOOK_BASE_URL in backend/.env with the ngrok URL
```

## Required Environment Variables (backend/.env)

```
DATABASE_URL=postgresql://synth:synth@localhost:5432/synth
ANTHROPIC_API_KEY=...
RECALL_API_KEY=...
WEBHOOK_BASE_URL=https://your-ngrok-url.ngrok-free.dev
SERPER_API_KEY=...
DEEPGRAM_API_KEY=...
SECRET_KEY=...              # JWT signing key (REQUIRED in production)
WEBHOOK_SECRET=...          # Recall.ai webhook auth token (recommended)
CORS_ORIGINS=http://localhost:3000  # Comma-separated allowed origins
ENVIRONMENT=development     # Set to "production" for strict startup validation
```

## Architecture

```
Recall.ai bot in meeting
    |
    v
Deepgram Nova-3 (streaming transcription)
    |
    v
Webhook -> bot_engine.process_webhook_transcript()
    |
    +--> Wake word detection ("Hey Assistant", 14 phonetic variants)
    +--> Context assembly:
    |      1. Rolling summary (LLM-compressed, big picture)
    |      2. Raw buffer (structured, last 5 min, speaker + type tags)
    |      3. RAG search (ChromaDB, document + old transcript chunks)
    |      4. Web search (Serper, if needed)
    |
    +--> Smart filler sent immediately (25 phrases, 6 categories, pre-cached MP3)
    +--> Claude Haiku 4.5 generates response
    +--> Kokoro TTS synthesizes audio
    +--> Recall.ai sends audio to meeting
```

## Key Files

### Bot Engine (the orchestrator)
- `backend/app/core/bot_engine.py` - Main pipeline: wake word -> filler -> context -> LLM -> TTS -> audio
- `backend/app/api/routes/webhook.py` - Recall.ai webhook receiver, echo detection, greeting

### Context & Memory
- `backend/app/context/manager.py` - Assembles context for LLM (summary + buffer + RAG + docs)
- `backend/app/context/raw_buffer.py` - Structured transcript buffer (speaker, timestamp, type tags)
- `backend/app/context/rolling_summary.py` - LLM-compressed meeting summary (updates every 500 chars)
- `backend/app/context/rag.py` - ChromaDB vector store for document chunks + old transcript

### Audio Pipeline
- `backend/app/core/tts.py` - Kokoro TTS wrapper (am_michael voice)
- `backend/app/core/vad.py` - Silero VAD (per-session instances)
- `backend/app/core/stt.py` - Whisper large-v3 (not used in webhook path)

### Intelligence
- `backend/app/core/llm.py` - Claude Haiku 4.5 client (sync, async, streaming)
- `backend/app/core/search.py` - Serper + SearXNG web search
- `backend/app/core/insight_detector.py` - Background fact-checking

### Wake Word & Fillers
- `backend/app/utils/wake_word.py` - "Hey Assistant" detection with 14 phonetic variants
- `backend/app/utils/filler.py` - 25 context-aware filler phrases across 6 categories
- `backend/app/utils/query_router.py` - QueryCategory classification + web search routing
- `backend/app/utils/prompt_builder.py` - System prompt (5 sections: identity, voice, knowledge, etiquette, personality)

### Meeting Management
- `backend/app/meeting/recall_client.py` - Recall.ai API (create bot, send audio, stop audio)
- `backend/app/meeting/session.py` - Meeting session state machine

## Key Configuration Values

- Wake word: `"hey assistant"` (configurable per agent via `agent_config.wake_word`)
- TTS voice: `am_michael` (male)
- Follow-up window: 8 seconds after audio playback ends
- Question collect time: 1.0 second
- Buffer window: 5 minutes (structured with speaker grouping + type detection)
- RAG embed flush: 200-word chunks or 2-minute stale threshold
- RAG search distance threshold: 1.0 (cosine distance, results above filtered out)
- Context budget: 8000 tokens (20% summary, 30% buffer, 20% doc summaries, 30% RAG)
- Token estimation: words * 1.5 (conservative multiplier)
- Webhook concurrency: max 20 concurrent tasks (asyncio.Semaphore)
- ChromaDB persist path: absolute, anchored to `backend/chroma_data/`

## Testing

```bash
cd backend
python3 -m pytest tests/test_audio_pipeline.py tests/test_search_routing.py -v -k "not slow and not SearchClientResults and not VisionProcessor"
```

25 tests covering: wake word detection, buffer operations, filler system, query routing, prompt builder.

## Critical Rules

- **Never edit backend files during a live meeting** - `--reload` wipes all in-memory sessions. The bot stops responding until a new meeting is started.
- **Never commit .env, API keys, or chroma_data/** - use .env.example for documentation.
- **Recall.ai API quirks**: Provider key is `deepgram_streaming` (not `deepgram`). Boolean values must be strings (`"true"` not `True`). Extra Deepgram params go in `extra_params` dict. `bot.status_change` is not a valid webhook event.
- **Echo detection**: All `Unknown` and empty speaker transcripts are dropped (bot's own speech echoed by Recall.ai).
- **Interruption**: Bot stays in RESPONDING during playback, polls every 300ms. Calls `stop_output_audio` on participant speech or stop phrases ("thank you", "stop", "enough").
- **PRs go to CongaraWorld/Synth** (upstream), not the personal fork. Follow CONTRIBUTING.md (issue first, @copilot mention, verification steps).

## Security Architecture

- **Webhook auth**: `X-Webhook-Secret` header validated with `hmac.compare_digest()` (timing-safe). Backward-compatible when `WEBHOOK_SECRET` is unset.
- **CORS**: Configurable origins via `CORS_ORIGINS` env var (default `http://localhost:3000`). Never `["*"]` with credentials.
- **WebSocket auth**: JWT token required via `?token=` query param. Validates expiry, user identity, and session ownership (IDOR protection).
- **Credit operations**: Atomic SQL `UPDATE...WHERE credits >= N` pattern prevents double-spend from concurrent requests.
- **Startup validation**: In production (`ENVIRONMENT=production`), missing `SECRET_KEY`, `RECALL_API_KEY`, or `ANTHROPIC_API_KEY` crashes the app at startup.
- **Password policy**: Min 8 chars, requires uppercase + lowercase + digit.
- **File uploads**: Extension allowlist (pdf, docx, txt) + magic byte validation + path traversal protection.
- **Security headers**: X-Content-Type-Options, X-Frame-Options, Referrer-Policy, Permissions-Policy on all responses.

## Concurrency Model

- **Per-session processing lock**: `asyncio.Lock` per session prevents concurrent `_handle_question` calls for the same meeting.
- **Double-checked model init**: `_lazy_load_models()` uses `asyncio.Lock` with double-check pattern — safe for concurrent greeting + join races.
- **Session tracking**: `_ensure_session_tracking()` called from ALL session creation paths (join, recover, REST API, webhook safety net).
- **Thread-safe memory**: `RollingSummary` uses `threading.Lock`; `RawTranscriptBuffer` uses `threading.Lock`; `RAGPipeline._encode()` serializes all SentenceTransformer calls.
- **No nested locks**: `flush_remaining_embeddings()` acquires raw_buffer lock and embed lock sequentially, never nested.
- **Deque overflow protection**: Entries evicted by `maxlen=200` are captured and routed to the embed buffer before loss.

## Current State

Phases 1-9 complete. Phase 10 (production hardening) applied: 43 audit issues fixed across concurrency, memory pipeline, and security. PR #32 open on CongaraWorld/Synth with Phase 9 features.
