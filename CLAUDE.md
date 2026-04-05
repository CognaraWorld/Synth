# Synth - Project Context

## What This Is

AI meeting bot that joins Zoom/Teams/Google Meet as a voice participant. Listens to the meeting, answers questions when invoked ("Nova"), reads uploaded documents, searches the web, OCRs screen shares, and delivers post-meeting summaries. Remembers across meetings.

## Tech Stack

| Layer | Technology | Notes |
|---|---|---|
| Backend | Python 3.12, FastAPI, SQLAlchemy (async), PostgreSQL | `backend/app/` |
| Frontend | Next.js 16.2.2 (App Router), React 19, Tailwind v4, shadcn/ui | `frontend/` |
| LLM | Gemini 2.5 Flash Lite (primary), Claude Haiku 4.5 (fallback) | Gemini for Q&A, Claude for summaries/streaming |
| Transcription | Deepgram Nova-3 via Recall.ai (streaming) | Keyword boost `Nova:5` |
| TTS | Kokoro (am_michael voice, 24kHz, 1.1x speed) | Pre-loaded at startup |
| VAD | Silero (per-session instances) | Only used in direct audio path |
| Search | Serper (speculative parallel, skipped for meeting questions) | Smart routing via skip/force markers |
| Vector DB | ChromaDB (BAAI/bge-large-en-v1.5 embeddings) | Per-agent collections, hybrid search |
| Vision/OCR | Gemini Flash vision (primary), Claude vision (fallback) | Screen share OCR |
| Meeting Infra | Recall.ai API | Bot deployment + audio + webhooks + screen capture |

## Running Locally

```bash
# Backend (requires PostgreSQL running on localhost:5432)
cd backend
source .venv/bin/activate
TOKENIZERS_PARALLELISM=false uvicorn app.main:app --host 0.0.0.0 --reload --port 8000

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
GEMINI_API_KEY=...
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
Deepgram Nova-3 (streaming transcription) + Screen Share Capture
    |
    v
Webhook -> bot_engine.process_webhook_transcript()
    |
    +--> Wake word detection ("Nova", phonetic variants: nora, noah, mova, rover)
    |      + Split-chunk merge ("Hey" held + "Nova" combined within 2s)
    |
    +--> Query rewriting (resolves "he", "she", "that" → specific names/topics)
    +--> Context assembly (16K token budget):
    |      1. Past meeting summaries (10% — cross-meeting memory)
    |      2. Rolling summary (15% — LLM-compressed, updates every 300 chars)
    |      3. Raw buffer (25% — structured, last 10 min, speaker + type tags)
    |      4. Document summaries (20% — uploaded doc overviews)
    |      5. RAG hybrid search (30% — semantic + keyword, documents + old transcript)
    |      + Entity tracking (people, decisions, action items)
    |      + Speculative web search (parallel, included if relevant)
    |
    +--> Filler sent immediately (7 natural phrases, pre-cached MP3)
    +--> Gemini 2.5 Flash Lite generates response (Claude Haiku fallback)
    +--> Kokoro TTS synthesizes audio
    +--> Recall.ai sends audio to meeting
    
Screen Share:
    Recall.ai captures screenshot → Gemini vision OCR → added to context as [Screen Share]
```

## Key Files

### Bot Engine (the orchestrator)
- `backend/app/core/bot_engine.py` - Main pipeline: wake word -> filler -> context -> LLM -> TTS -> audio
- `backend/app/api/routes/webhook.py` - Recall.ai webhook receiver, echo detection, greeting, screenshot OCR

### Context & Memory
- `backend/app/context/manager.py` - Context assembly (5 layers + entities + query rewriting)
- `backend/app/context/raw_buffer.py` - Structured transcript buffer (speaker, timestamp, type tags)
- `backend/app/context/rolling_summary.py` - LLM-compressed meeting summary (updates every 300 chars)
- `backend/app/context/rag.py` - ChromaDB vector store with hybrid search (semantic + keyword)
- `backend/app/context/documents.py` - Document parsing + chunking + embedding

### Audio & Vision
- `backend/app/core/tts.py` - Kokoro TTS wrapper (am_michael voice)
- `backend/app/core/vad.py` - Silero VAD (per-session instances)
- `backend/app/core/vision.py` - Screen share OCR (Gemini vision primary, Claude fallback)
- `backend/app/core/stt.py` - Whisper large-v3 (not used in webhook path)

### Intelligence
- `backend/app/core/llm.py` - Hybrid LLM: Gemini Flash Lite (primary) + Claude Haiku (fallback + heavy tasks)
- `backend/app/core/search.py` - Serper web search (smart routing: skip for meeting questions, force for "search"/"research")
- `backend/app/core/insight_detector.py` - Background fact-checking

### Wake Word & Fillers
- `backend/app/utils/wake_word.py` - "Nova" detection with phonetic variants + "Hey" split-chunk merge
- `backend/app/utils/filler.py` - 7 natural filler phrases (universal: "Sure.", "One sec.", "Hmm.", etc.)
- `backend/app/utils/query_router.py` - QueryCategory classification
- `backend/app/utils/prompt_builder.py` - System prompt (5 sections: identity, voice, knowledge, etiquette, personality)

### Meeting Management
- `backend/app/meeting/recall_client.py` - Recall.ai API (create bot, send audio, stop audio, screen capture)
- `backend/app/meeting/session.py` - Meeting session state machine

## Key Configuration Values

- Wake word: `"nova"` (configurable per agent via `agent_config.wake_word`)
- TTS voice: `am_michael` (male, persona-aware via `get_persona_tts_voice()`)
- Follow-up window: 8 seconds after audio playback ends
- Follow-up minimum: 4 words + coherence marker (prevents garbled fragments)
- Question collect time: 0.5 seconds (skipped for 4+ word questions)
- Buffer window: 10 minutes (structured with speaker grouping + type detection)
- Rolling summary interval: 300 characters
- RAG embed flush: 200-word chunks or 2-minute stale threshold
- RAG search: hybrid (semantic + keyword), distance threshold 1.0, top 8 results
- Context budget: 16,000 tokens (10% past meetings, 15% summary, 25% buffer, 20% docs, 30% RAG)
- Token estimation: words * 1.5 (conservative multiplier)
- Utterance end: 700ms (Deepgram silence detection)
- Webhook concurrency: max 20 concurrent tasks (asyncio.Semaphore)
- Stale bot timeout: 2 hours (auto-killed by background task)
- ChromaDB persist path: absolute, anchored to `backend/chroma_data/`

## Billing

- **Minute-based billing**: Users have a minutes balance. No upfront deduction.
- Meeting start: checks balance >= 5 minutes minimum.
- Meeting end: calculates actual duration (rounded up), deducts from balance.
- New users get 60 free minutes on registration.
- Auto-kill: stale bots (>2hr) auto-stopped. Meeting end webhook auto-stops bot.
- Cost per minute: ~₹2.3 ($0.027) — Recall ₹1.70, Deepgram ₹0.34, LLM ₹0.17, Serper ₹0.08

## Testing

```bash
cd backend
python3 -m pytest tests/test_audio_pipeline.py tests/test_search_routing.py -v -k "not slow and not SearchClientResults and not VisionProcessor"
```

25 tests covering: wake word detection, buffer operations, filler system, query routing, prompt builder.

## Critical Rules

- **Never edit backend files during a live meeting** — `--reload` wipes all in-memory sessions. The bot stops responding until a new meeting is started.
- **Never commit .env, API keys, or chroma_data/** — use .env.example for documentation.
- **Recall.ai API quirks**: Provider key is `deepgram_streaming` (not `deepgram`). Boolean values must be strings (`"true"` not `True`). Extra Deepgram params go in `extra_params` dict. `bot.status_change` is not a valid webhook event for realtime_endpoints.
- **Echo detection**: Speaker filter (Unknown/""/bot) + text-based word overlap (60% threshold) + quality filter (3+ words, wake words exempt).
- **Interruption**: Bot stays in RESPONDING during playback, polls every 300ms using actual PCM duration. Calls `stop_output_audio` on participant speech or stop phrases.
- **PRs go to CognaraWorld/Synth** (upstream), not the personal fork. Follow CONTRIBUTING.md.

## Security Architecture

- **Webhook auth**: `X-Webhook-Secret` header validated with `hmac.compare_digest()` (timing-safe). Backward-compatible when unset.
- **CORS**: Configurable origins via `CORS_ORIGINS` env var (default `http://localhost:3000`). Never `["*"]` with credentials.
- **WebSocket auth**: JWT token via `?token=` query param. Fail-closed: rejects unknown sessions. Validates expiry, user identity, session ownership (IDOR protection). Rejects default insecure key.
- **Credit operations**: Atomic SQL `UPDATE...WHERE` pattern. Minute-based billing calculated on meeting end.
- **Startup validation**: In production (`ENVIRONMENT=production`), missing secrets crash the app at startup.
- **Password policy**: Min 8 chars, requires uppercase + lowercase + digit.
- **File uploads**: Extension allowlist (pdf, docx, txt) + magic byte validation + path traversal protection.
- **Security headers**: X-Content-Type-Options, X-Frame-Options, Referrer-Policy, Permissions-Policy.

## Concurrency Model

- **Per-session processing lock**: `asyncio.Lock` per session prevents concurrent `_handle_question` calls.
- **Double-checked model init**: `_lazy_load_models()` uses `asyncio.Lock` with double-check pattern.
- **Session tracking**: `_ensure_session_tracking()` called from ALL session creation paths.
- **Thread-safe memory**: `RollingSummary` uses `threading.Lock`; `RawTranscriptBuffer` uses `threading.Lock`; `RAGPipeline._encode()` serializes all SentenceTransformer calls.
- **No nested locks**: All lock acquisitions are sequential, never nested.
- **Deque overflow protection**: Entries evicted by `maxlen=200` captured and routed to embed buffer.

## Memory Architecture

```
Layer 1: Raw Buffer (10 min verbatim, deque maxlen=200)
    ↓ overflow/age eviction
Layer 2: Embed Buffer → ChromaDB (200-word chunks, hybrid search)
    ↑ also receives document chunks
Layer 3: Rolling Summary (LLM-compressed, full meeting history)
Layer 4: Entity Tracker (people, decisions, action items — keyword-based)
Layer 5: Past Meeting Summaries (cross-meeting memory from DB)
Layer 6: Query Rewriting (resolves pronouns → specific names/topics before RAG search)
```

## Current State

Phase 10 (production hardening) complete. 43 audit issues + 10 review findings fixed. PR #37 on CognaraWorld/Synth with all changes. Features: Gemini LLM, hybrid RAG, cross-meeting memory, entity tracking, query rewriting, screen share OCR, minute-based billing, auto-stop stale bots, natural fillers, Nova wake word.
