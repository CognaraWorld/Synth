# Synth - Project Context

## What This Is

AI meeting bot that joins Zoom/Teams/Google Meet as a voice participant. Listens to the meeting, answers questions when invoked ("Nova"), reads uploaded documents, searches the web, and delivers post-meeting summaries. Remembers across meetings. 5 persona presets (general, strategist, analyst, challenger, facilitator).

## Tech Stack

| Layer | Technology | Notes |
|---|---|---|
| Backend | Python 3.12, FastAPI, SQLAlchemy (async), PostgreSQL | `backend/app/` |
| Frontend | Next.js 14.2.5 (App Router), React 18.3.1, Tailwind 3.4.7, shadcn/ui | `frontend/` |
| LLM | Gemini 2.5 Flash Lite (primary), Claude Haiku 4.5 (fallback) | Gemini for Q&A, Claude for summaries/streaming |
| Transcription | Deepgram Nova-3 via Recall.ai (streaming) | Keyword boost `Nova:5` |
| TTS | Kokoro (persona-bound voices, 24kHz, 1.1x speed) | Pre-loaded at startup, synthesis in thread executor |
| VAD | Silero (per-session instances) | Only used in direct audio path |
| Search | Serper (speculative parallel, context-aware queries) | Plain text results (no markdown for TTS) |
| Vector DB | ChromaDB (shared BAAI/bge-large-en-v1.5 singleton) | Per-agent collections, cosine distance, hybrid search |
| Vision/OCR | Gemini Flash vision (primary), Claude vision (fallback) | Screen share OCR (PR #42 pending) |
| Meeting Infra | Recall.ai API (ap-northeast-1 region) | Bot deployment + audio + webhooks |
| Personas | 5 fixed presets with persona-bound TTS voices | `bot_profiles.py`, `prompt_builder.py` |

## Running Locally

```bash
# Backend (requires PostgreSQL running on localhost:5432)
cd backend
source .venv/bin/activate
TOKENIZERS_PARALLELISM=false uvicorn app.main:app --host 0.0.0.0 --reload --port 8000

# Frontend
cd frontend
npm run dev
```

### Production webhook ingress

For Recall.ai to deliver webhooks, the backend needs a public HTTPS URL. Two supported options:

- **Cloudflare Tunnel** (recommended) — see `docs/INGRESS.md` for setup.
- **Local development** — use Cloudflare Tunnel with a `dev.*` hostname, or (for quick testing) `cloudflared tunnel --url http://localhost:8000` which issues a temporary `*.trycloudflare.com` URL.

Set `WEBHOOK_BASE_URL` in `backend/.env` to your stable tunnel hostname.

## Required Environment Variables (backend/.env)

```
DATABASE_URL=postgresql://synth:synth@localhost:5432/synth
ANTHROPIC_API_KEY=...
GEMINI_API_KEY=...
RECALL_API_KEY=...
RECALL_REGION=ap-northeast-1
WEBHOOK_BASE_URL=https://synth-webhook.yourdomain.com
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
    +--> Wake word detection ("Nova", phonetic variants: nora, noah, mova)
    |      + Leading/trailing word boundary check (blocks "supernova", "innova")
    |      + Split-chunk merge ("Hey" held + "Nova" combined within 2s)
    |
    +--> Query rewriting (expands ALL short questions with recent topic context)
    |      Resolves pronouns (he/she/they/their/them/its/his/her)
    |      Adds conversation topics for follow-up context
    |      Used by BOTH RAG search AND web search
    |
    +--> Context assembly (16K token budget, tiktoken-accurate):
    |      1. Past meeting summaries (10% - cross-meeting memory)
    |      2. Rolling summary (15% - hierarchical with anchored key facts)
    |      3. Raw buffer (25% - last 10 min, 400 entries, speaker + type tags)
    |      4. Document summaries (20% - uploaded doc overviews)
    |      5. RAG hybrid search (30% - separate transcript/document queries)
    |      + Entity tracking (people, decisions, action items)
    |      + Scope-isolated metadata (meeting_id, agent_id, user_id)
    |      + Web search (parallel, context-aware queries, plain text results)
    |
    +--> Bot response stored in transcript buffer (enables follow-up context)
    +--> Filler sent immediately (7 phrases, voice-aware cache per persona)
    +--> Gemini 2.5 Flash Lite generates response (30s timeout, Claude fallback)
    +--> Kokoro TTS synthesizes audio in thread executor (non-blocking)
    +--> Recall.ai sends audio to meeting
    +--> Follow-up window opens (8s, closed by stop phrases)
```

## Key Files

### Bot Engine (the orchestrator)
- `backend/app/core/bot_engine.py` - Main pipeline: wake word -> filler -> context -> LLM -> TTS -> audio
- `backend/app/api/routes/webhook.py` - Recall.ai webhook receiver, echo detection, greeting, auto-stop

### Context & Memory
- `backend/app/context/manager.py` - Context assembly (scope-isolated, tiktoken, separate doc/transcript queries)
- `backend/app/context/raw_buffer.py` - Structured transcript buffer (400 entries, 10 min, speaker grouping)
- `backend/app/context/rolling_summary.py` - Hierarchical summary with anchored key facts
- `backend/app/context/rag.py` - ChromaDB with shared model singleton, cosine distance, metadata filters, deletion
- `backend/app/context/documents.py` - PDF table extraction, structure-aware chunking, scope metadata

### Audio & Vision
- `backend/app/core/tts.py` - Kokoro TTS wrapper (persona-bound voices)
- `backend/app/core/vad.py` - Silero VAD (per-session instances)
- `backend/app/core/vision.py` - Screen share OCR (Gemini primary, Claude fallback)
- `backend/app/core/stt.py` - Whisper large-v3 (not used in webhook path)

### Intelligence
- `backend/app/core/llm.py` - Hybrid LLM with question-first prompts, 30s timeout, graceful fallback
- `backend/app/core/search.py` - Serper web search (plain text output, context-aware queries)
- `backend/app/core/insight_detector.py` - Background fact-checking

### Personas & Profiles
- `backend/app/utils/prompt_builder.py` - 5 persona presets with behavioral directives
- `backend/app/utils/bot_profiles.py` - Persona voice mapping, system prompt builder
- `backend/app/api/routes/bot.py` - Bot profile CRUD
- `backend/app/meeting/live_control.py` - Live session controls

### Wake Word & Fillers
- `backend/app/utils/wake_word.py` - "Nova" detection with phonetic variants + word boundary checks
- `backend/app/utils/filler.py` - 7 filler phrases with voice-aware cache (per persona)
- `backend/app/utils/query_router.py` - QueryCategory classification

### Meeting Management
- `backend/app/meeting/recall_client.py` - Recall.ai API (create bot, send audio, stop audio)
- `backend/app/meeting/session.py` - Meeting session state machine (scope IDs propagated to ContextManager)

## Key Configuration Values

- Wake word: `"nova"` (configurable per agent via `agent_config.wake_word`)
- TTS voice: persona-bound (general=af_heart, strategist=am_adam, challenger=am_michael, etc.)
- Follow-up window: 8 seconds after audio playback ends (closed by stop phrases)
- Follow-up minimum: 4 words + coherence marker (prevents garbled fragments)
- Stop phrases: "thank you", "thanks", "stop", "enough", "got it", etc. — kills audio + closes follow-up window
- Question collect time: 0.5 seconds (skipped for 4+ word questions)
- Buffer: 10 minutes, 400 entries max (structured with speaker grouping + type detection)
- Rolling summary: 300 char interval, hierarchical with anchored key facts
- RAG: shared embedding model, cosine distance, separate transcript/document queries
- RAG embed flush: 200-word chunks or 2-minute stale threshold
- Context budget: 16,000 tokens (tiktoken cl100k_base, binary search truncation)
- Token counting: tiktoken (accurate), fallback words * 1.5
- Utterance end: 700ms (Deepgram silence detection)
- Webhook concurrency: max 20 concurrent tasks (asyncio.Semaphore)
- Stale bot timeout: 2 hours (auto-killed by background task)
- Orphaned bot cleanup: runs on every server startup (prevents billing leaks from --reload)
- ChromaDB: shared PersistentClient, per-agent collections, cosine distance

## Billing

- **Minute-based billing**: Users have a minutes balance. 5-minute atomic reserve on start.
- Meeting start: reserves 5 minutes atomically (prevents overdraw).
- Meeting end: calculates actual duration, settles delta (charges extra or refunds).
- Idempotent billing: `UPDATE WHERE credits_used=0` guard prevents double-deduct across stop/webhook/cleanup paths.
- `credits_used` column default is `0` (matches billing guard).
- New users get 60 free minutes on registration.
- Auto-kill: stale bots (>2hr) auto-stopped. Meeting end webhook auto-stops bot.
- Orphan protection: `_stop_orphaned_bots()` runs on startup — kills bots left by `--reload`.
- Cost per hour: ~$1.05 — Recall $0.50/hr, Deepgram ~$0.26/hr, LLM ~$0.10/hr, Serper ~$0.05/hr

## Testing

```bash
cd backend
source .venv/bin/activate
TOKENIZERS_PARALLELISM=false python3 -m pytest tests/ -k "not slow and not SearchClientResults and not VisionProcessor" -v
```

166 tests covering: wake word detection, buffer operations, filler system, query routing, prompt builder, context assembly, memory isolation, billing, agent CRUD, meeting lifecycle, reports, payments, persona prompts, live sessions, ingress hardening.

## Critical Rules

- **Never edit backend files during a live meeting** — `--reload` wipes all in-memory sessions. Orphaned bot cleanup on restart mitigates billing leaks but the session state is lost.
- **Never commit .env, API keys, or chroma_data/**
- **Recall.ai API quirks**: Provider key is `deepgram_streaming`. Boolean values must be strings. `bot.status_change` is not a valid webhook event. Region is `ap-northeast-1`.
- **Echo detection**: Speaker filter (Unknown/""/bot) + text-based word overlap (60% threshold) + quality filter (3+ words, wake words exempt).
- **Interruption**: Bot stays in RESPONDING during playback, polls every 300ms using actual PCM duration. Calls `stop_output_audio` on participant speech or stop phrases.
- **Stop phrases close follow-up window**: "thank you", "thanks", "stop" etc. kill audio AND clear `_last_response_time` so bot stops listening for follow-ups.
- **Bot responses stored in buffer**: After answering, the bot's response is added to the transcript buffer so follow-up questions have full Q&A context.
- **Agent deletion cascades**: Deletes documents (disk + ChromaDB embeddings), meetings, summaries, usage records, overrides.
- **PRs go to CognaraWorld/Synth** (upstream). Follow CONTRIBUTING.md.

## Security Architecture

- **Webhook auth**: `hmac.compare_digest()` (timing-safe). Backward-compatible when unset.
- **CORS**: Configurable via `CORS_ORIGINS` (default `http://localhost:3000`).
- **WebSocket auth**: JWT via `?token=`. Fail-closed. IDOR ownership check. Rejects default insecure key.
- **Credit operations**: Atomic reserve + idempotent settlement across 3 billing paths.
- **Startup validation**: Production mode blocks on missing secrets.
- **Startup orphan cleanup**: Stops any Recall bots left running after restart.
- **Password policy**: Min 8 chars, uppercase + lowercase + digit.
- **File uploads**: Extension allowlist + magic byte validation + path traversal protection.
- **Security headers**: X-Content-Type-Options, X-Frame-Options, Referrer-Policy, Permissions-Policy.

## Concurrency Model

- **Per-session processing lock**: `asyncio.Lock` per session prevents concurrent question handling.
- **Double-checked model init**: `_lazy_load_models()` with `asyncio.Lock`.
- **TTS lock**: `_tts_lock` serializes voice switching + synthesis in thread executor.
- **Session tracking**: `_ensure_session_tracking()` from ALL creation paths.
- **Thread-safe memory**: `_state_lock` protects entities/summaries across event loop and thread executor. RollingSummary, RawTranscriptBuffer, RAGPipeline all locked.
- **Shared embedding model**: Module-level `_encode_lock` serializes all SentenceTransformer calls.
- **No nested locks**: All acquisitions sequential.
- **Deque overflow protection**: Evicted entries routed to embed buffer.

## Memory Architecture

```
Layer 1: Raw Buffer (10 min verbatim, deque maxlen=400)
    ↓ overflow/age eviction
Layer 2: Embed Buffer → ChromaDB (200-word chunks, scope metadata, cosine search)
    ↑ also receives document chunks (with document_id, agent_id, user_id)
Layer 3: Rolling Summary (hierarchical: prose + anchored key facts list)
Layer 4: Entity Tracker (people, decisions, action items — keyword-based, persisted on meeting end)
Layer 5: Past Meeting Summaries (cross-meeting memory from DB, last 3, loaded on startup + recovery)
Layer 6: Query Rewriting (expands ALL short questions with recent topic context, not just pronouns)
Layer 7: Bot Response Injection (bot's own answers added to buffer for follow-up context)

Scope Isolation:
- Every chunk tagged with meeting_id, agent_id, user_id, source_type
- Separate queries for current-meeting transcript, archived transcript, and documents
- Legacy metadata fallback (source: "document" | source: "meeting_transcript")
- Document deletion removes embeddings from ChromaDB via delete_by_metadata()
- Agent deletion clears entire ChromaDB collection + disk files
```

## LLM Prompt Structure

```
System: [persona system prompt with behavioral guidelines]

User: A meeting participant just asked you this question:
      "[question]"

      Answer the question directly. Do NOT repeat, narrate, or summarize
      the question. Do NOT say who asked it. Just give the answer. Combine
      information from ALL available sources — documents, web search results,
      meeting conversation, and your own knowledge.

      Here is the meeting context you can reference:
      === PAST MEETINGS ===
      === MEETING SUMMARY ===
      === TRACKED ENTITIES ===
      === RECENT CONVERSATION (last 10 minutes) ===
      === DOCUMENT OVERVIEWS ===
      === PRIMARY SOURCE ===
      === WEB SEARCH RESULTS ===
```

## PR Status

- **#37** — merged (production hardening + Gemini LLM)
- **#34** — merged (schema drift hardening)
- **#36** — merged (5 fixed personas)
- **#38** — closed (superseded by #42)
- **#39** — closed (superseded by #41)
- **#41** — open (cross-meeting memory, hybrid RAG, minute billing, entity tracking)
- **#42** — open (screenshare capture pipeline — Devyansh, pending fixes)

## Current State

Phase 10+ complete. Full codebase audit and hardening session (Apr 5, 2026): 50+ fixes across backend core, memory system, frontend, and tests. Key improvements: event loop non-blocking (TTS/embedding in executors), LLM timeout + graceful fallback, scope-isolated RAG with shared model, hierarchical rolling summaries, tiktoken budgeting, context-aware web search, orphaned bot cleanup on startup, full cascade delete, 166 tests passing. Screen share OCR pipeline pending in PR #42.
