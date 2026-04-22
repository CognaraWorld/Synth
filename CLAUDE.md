# Synth - Project Context

## What This Is

AI meeting bot that joins Zoom/Teams/Google Meet as a voice participant. Listens to the meeting, answers questions when invoked (default wake word: **"Nova"**, plus optional "Hey Synth" / "Hey Assistant" / custom), reads uploaded documents, searches the web, and delivers post-meeting summaries. Remembers across meetings. 5 persona presets (general, strategist, analyst, challenger, facilitator).

## Tech Stack

| Layer | Technology | Notes |
|---|---|---|
| Backend | Python 3.12, FastAPI, SQLAlchemy (async), PostgreSQL | `backend/app/` |
| Frontend | Next.js 14.2.5 (App Router), React 18.3.1, Tailwind 3.4.7, shadcn/ui | `frontend/` |
| LLM | Gemini 2.5 Flash Lite (primary), Claude Haiku 4.5 (fallback) | Three streaming paths: Gemini native async → Gemini sync-bridge executor → Claude async |
| Transcription | Deepgram Nova-3 via Recall.ai (streaming) | Keyword boost `Nova:5,Hey Nova:5,nova:5`; utterance end 700 ms |
| TTS | Kokoro ONNX (persona-bound voices, 24 kHz int16, 1.1× speed) | Pre-loaded at startup, synthesis in thread executor |
| VAD | Silero (per-session instances, 16 kHz, threshold 0.5) | Only used in direct audio path (not webhook) |
| Search | Serper (Google) → SearXNG fallback | Plain-text results (no markdown) for TTS safety |
| Vector DB | ChromaDB (shared `BAAI/bge-large-en-v1.5` singleton, cosine) | Per-agent collections, hybrid (semantic + `$contains` keyword) |
| Vision/OCR | Gemini 2.5 Flash Lite (primary), Claude Haiku 4.5 (fallback) | Screen share OCR; gated until video pipeline lands |
| Meeting Infra | Recall.ai API (region from `RECALL_REGION`, project uses `ap-northeast-1`) | Bot deployment + audio + webhooks |
| Audio out | ffmpeg via pydub (PCM int16 24 kHz → MP3 64 kbps base64) | **Startup probe** in `main.py` fails fast if ffmpeg missing |
| Personas | 5 fixed presets, persona-bound TTS voices | `bot_profiles.py`, `prompt_builder.py` |

## Running Locally

```bash
# Backend (requires PostgreSQL on localhost:5432 and ffmpeg on PATH)
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
RECALL_REGION=ap-northeast-1
WEBHOOK_BASE_URL=https://your-ngrok-url.ngrok-free.dev
SERPER_API_KEY=...
DEEPGRAM_API_KEY=...
SECRET_KEY=...                  # JWT signing key (REQUIRED in production)
WEBHOOK_SECRET=...              # Recall.ai webhook auth token (whsec_... preferred)
BACKEND_SERVICE_SECRET=...      # Frontend↔backend service-token exchange
CORS_ORIGINS=http://localhost:3000  # Comma-separated allowed origins
ENVIRONMENT=development         # Set to "production" for strict startup validation
```

`ffmpeg` must be installed and on `PATH`. Startup will refuse to boot in `ENVIRONMENT=production` if the ffmpeg probe fails (`main.py:check_ffmpeg_available`).

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
    +--> Wake word detection (default "nova"; also "hey synth", "hey assistant", custom)
    |      Two paths in wake_word.py:
    |        1) Fast path: exact substring + isalnum() word-boundary on both sides
    |        2) Fuzzy path: LRU-cached regex with phonetic variants (nora/mova/sint/...)
    |      Word boundary blocks "supernova", "innova", etc.
    |      is_directed_at_other(): silences bot when addressee is a proper name (not bot alias / generic group)
    |
    +--> Echo filter (echo_tracker.py)
    |      Speaker filter (Unknown/""/bot) + 60% word-overlap on last 5 outputs
    |
    +--> Query rewriting (manager._rewrite_query)
    |      Vague pronouns (he/she/they/their/them/its/his/her/that/this/it) trigger expansion
    |      Adds last 3 speakers + topic words (>4 chars, not in SKIP_WORDS) for short questions (<10 words)
    |      Used by BOTH RAG search AND web search routing
    |
    +--> Context assembly (16K token budget, tiktoken cl100k_base, binary-search truncation):
    |      10% past meeting summaries (cross-meeting memory)
    |      15% rolling summary (hierarchical: prose + anchored key facts, capped at 20)
    |      25% raw buffer (last 10 min, deque maxlen=400, speaker grouping + type tags)
    |      10% document summaries (uploaded doc overviews)
    |      20% shared screen content (Gemini Vision OCR, last N entries up to budget)
    |      20% RAG hybrid search (semantic + keyword, scope-filtered by meeting/agent/user)
    |      + Entity tracking (people, decisions, action items)
    |      + Web search injected as PRIMARY SOURCE (plain text)
    |
    +--> Filler dispatch (filler.py — 24 phrases across 6 QueryCategory pools)
    |      Categories: MEETING_RECAP, DOCUMENT, TECHNICAL, OPINION, WEB_SEARCH, GENERAL
    |      Voice-keyed cache `{phrase}:{voice}` so persona switch never reuses wrong audio
    |      Optional personalized variant ("Sure Yash, let me check.") when speaker name known
    |
    +--> LLM call (llm.py): Gemini 2.5 Flash Lite primary
    |      Path 1: native async stream (true I/O, no executor)
    |      Path 2: sync stream via ThreadPoolExecutor(max_workers=4) with orphan tracking (rejects new streams when ≥3 workers blocked >2s)
    |      Path 3: Claude Haiku 4.5 async fallback
    |      30s timeout (asyncio.timeout). Sentence-boundary streaming on .!? separators.
    |      max_output_tokens=1024 (Gemini), 4096 (Claude); temperature=0.7
    |
    +--> Kokoro TTS (tts.py): persona-bound voice, 24 kHz int16, thread executor (non-blocking)
    +--> recall_client.pcm_to_mp3_b64() → ffmpeg → base64 MP3 64kbps
    +--> Recall.ai send_audio_b64() (max_attempts=1 prevents replay-after-interrupt)
    +--> Bot response added back to raw buffer (enables follow-up context)
    +--> Follow-up window (8s) opens; closed by stop phrases or new utterance
    +--> Interrupt: double-stop with 150ms gap clears in-flight MP3 chunks
```

## Key Files

### Bot Engine (the orchestrator)
- `backend/app/core/bot_engine.py` — Main pipeline: wake word → filler → context → LLM → TTS → audio. `join_meeting()` accepts an optional `meeting_id` (DB UUID); generates a UUID if not provided. **Never** uses the meeting URL as scope.
- `backend/app/api/routes/webhook.py` — Recall.ai webhook receiver. Svix HMAC + legacy fallback, 300s replay window, `asyncio.Semaphore(50)` for bounded concurrency.

### Context & Memory
- `backend/app/context/manager.py` — `ContextManager` orchestrates all layers; 16K token budget with binary-search truncation; query rewriting; hybrid RAG with legacy metadata fallback.
- `backend/app/context/raw_buffer.py` — Structured deque (maxlen=400, 10-min sliding window), speaker grouping, type detection (statement/question/decision/action_item).
- `backend/app/context/rolling_summary.py` — LLM-driven incremental summary with anchored key facts (capped at 20). 300-char update threshold.
- `backend/app/context/rag.py` — ChromaDB shared `PersistentClient` at `{repo}/chroma_data/`; shared `BAAI/bge-large-en-v1.5` singleton with global `_encode_lock` (model is NOT thread-safe).
- `backend/app/context/documents.py` — PDF table extraction, structure-aware chunking (200-word target, paragraph boundaries), document summary via LLM (12k-word truncation).

### Audio & Vision
- `backend/app/core/tts.py` — Kokoro ONNX wrapper. Outputs PCM int16 mono at 24 kHz (so byte-rate = 48000 — the `len(pcm)/48000` math in `bot_engine.py:1130` is correct).
- `backend/app/core/vad.py` — Silero VAD per session (16 kHz, threshold 0.5).
- `backend/app/core/vision.py` — `VisionProcessor` with Gemini → Claude fallback (`auto`/`gemini`/`claude-vision` engines).
- `backend/app/core/stt.py` — Whisper large-v3 via faster-whisper (int8 quant). Not used in webhook path.

### Intelligence
- `backend/app/core/llm.py` — `LLMClient` with three streaming paths, orphan-tracked sync bridge, sentence buffering. 1 retry at 0.25 × (n+1) backoff.
- `backend/app/core/search.py` — Serper primary, SearXNG fallback. `search_formatted()` returns plain text (`"1. Title: Snippet"` form).
- `backend/app/core/insight_detector.py` — Background fact-check via 5 regex patterns + web search + Claude verification.

### Personas & Profiles
- `backend/app/utils/prompt_builder.py` — 5 persona presets with behavioral directives. `SUPPORTED_PERSONA_IDS = {general, strategist, analyst, challenger, facilitator}`.
- `backend/app/utils/bot_profiles.py` — `get_persona_tts_voice()` and `get_persona_voice_label()` mapping.
- `backend/app/api/routes/bot.py` — Bot profile CRUD.
- `backend/app/meeting/live_control.py` — Live session controls (mute, leave, instructions). Passes DB `meeting.id` to `engine.join_meeting()`.

### Wake Word & Fillers
- `backend/app/utils/wake_word.py` — Four phrase families: `nova`/`hey nova` (default + variants nora/noah/mova), `hey synth` (variants synth/sint/sent/since/sync/...), `hey assistant` (variants assistant/assistance/persistent/...), custom `hey <name>`. Fast path + fuzzy regex with `isalnum()` boundary check. `is_directed_at_other()` for proper-name detection.
- `backend/app/utils/filler.py` — **24 filler phrases across 6 `QueryCategory` pools** (MEETING_RECAP=4, DOCUMENT=4, TECHNICAL=4, OPINION=4, WEB_SEARCH=4, GENERAL=5). Voice-keyed cache. `get_personalized_filler()` adds first-name acknowledgment.
- `backend/app/utils/query_router.py` — `QueryCategory` classification + `needs_web_search()` gate.
- `backend/app/utils/followup_markers.py` — Coherence check for short follow-ups.

### Meeting Management
- `backend/app/meeting/recall_client.py` — Recall.ai client. String-boolean Deepgram params; provider key `deepgram_streaming`; `send_audio_b64` with `max_attempts=1`; double-stop interrupt; circuit breaker (5 fails → 30 s cooldown).
- `backend/app/meeting/session.py` — `MeetingSession` state machine. Constructor accepts `meeting_id` (DB UUID). Transitions: PENDING → JOINING → LISTENING ⇄ RESPONDING → ENDED (or → FAILED). `InvalidTransitionError` on disallowed edges.

## Key Configuration Values

- Wake words: 4 families (default `"nova"`; per-agent overridable in `agent_config.wake_word`)
- TTS voice mapping: `general=af_heart`, `strategist=am_adam`, `analyst=af_heart`, `challenger=am_michael`, `facilitator=af_heart`
- Follow-up window: 8 seconds after audio playback ends (closed by stop phrases)
- Follow-up minimum: 4 words + coherence marker
- Stop phrases: `"thank you"`, `"thanks"`, `"stop"`, `"enough"`, `"got it"`, … — kills audio AND clears `_last_response_time`
- Question collect time: 0.5 s (skipped for 4+ word questions)
- Raw buffer: 10 minutes, deque maxlen=400, speaker grouping + type detection
- Rolling summary: 300-char update threshold, anchored key facts capped at 20, pending buffer max 4000 chars
- RAG: shared embedding model (BAAI/bge-large-en-v1.5), cosine distance ≤ 1.0 filter, separate transcript/document queries, legacy metadata fallback
- RAG embed flush: 200-word chunks (10% overlap), 120-second stale threshold, 3 retry cycles
- Context budget: 16,000 tokens — split **10/15/25/10/20/20** (past meetings / rolling summary / raw buffer / doc summaries / shared screen / RAG hits)
- Token counting: tiktoken cl100k_base (accurate); fallback `words × 1.5`
- Utterance end: 700 ms (Deepgram silence detection)
- **Webhook concurrency: `asyncio.Semaphore(50)`** (`webhook.py:37`)
- Stale bot timeout: 7200 s (2 h) — checked every 300 s by background task
- Orphaned bot cleanup: runs on every server startup (prevents billing leaks from `--reload`)
- ChromaDB: shared `PersistentClient` at `{repo}/chroma_data/`, per-agent collections
- LLM: Gemini `max_output_tokens=1024`, `temperature=0.7`, 30 s timeout. Claude `max_tokens=4096`. 1 retry at 0.25 × (n+1) backoff
- TTS chunking: `max_chars=200`, `min_space_break=24` (`tts_chunks.py`)
- Echo tracker: 5 most-recent outputs per bot, 60% word-overlap threshold, 10-char minimum

## Billing

- **Minute-based billing**: users have a minutes balance. **5-minute atomic reserve on start**.
- Free tier: **60 minutes** on registration (`DEFAULT_STARTER_CREDITS = 60`).
- Atomic reserve: `UPDATE User SET credits = credits - 5 WHERE credits >= 5` — `rowcount==0` → 402 Insufficient credits.
- Settlement: `minutes_used = ceil(duration_seconds / 60)`, delta = `minutes_used - 5` against user.
- **Idempotent across all 3 settlement paths**: `UPDATE Meeting SET credits_used=N WHERE credits_used=0` (rowcount gates the user debit).
  - Path A: webhook terminal status (`call_ended`/`done`/`fatal`/`analysis_done`).
  - Path B: stale-bot cleanup (>2h, every 300s).
  - Path C: orphaned-bot cleanup on startup.
- Refund: `transaction_type='refund'` with unique index `(meeting_id) WHERE transaction_type='refund'` blocks double-refund.
- Credit packs (Stripe checkout): `pack_5=$30/5min`, `pack_20=$100/20min`, `pack_50=$200/50min`.
- Cost per hour: ~$1.05 — Recall $0.50/hr, Deepgram ~$0.26/hr, LLM ~$0.10/hr, Serper ~$0.05/hr.

## Testing

```bash
cd backend
source .venv/bin/activate
TOKENIZERS_PARALLELISM=false python3 -m pytest tests/ -k "not slow and not SearchClientResults and not VisionProcessor" -v
```

Test suite covers: wake word detection, buffer operations, filler system, query routing, prompt builder, context assembly, memory isolation, billing, agent CRUD, meeting lifecycle, reports, payments, persona prompts, live sessions, ingress hardening, **meeting_id scope isolation** (`test_meeting_id_scope.py`), **ffmpeg startup probe** (`test_ffmpeg_startup.py`), webhook security, screen capture, llm streaming.

## Critical Rules

- **Never edit backend files during a live meeting** — `--reload` wipes all in-memory sessions. Orphaned bot cleanup on restart mitigates billing leaks but session state is lost.
- **Never commit `.env`, API keys, or `chroma_data/`**.
- **Recall.ai API quirks**: Provider key is `deepgram_streaming`. Boolean values must be **strings** (`"true"`). `bot.status_change` is not a valid webhook event. Region from `RECALL_REGION`.
- **Echo detection**: Speaker filter (Unknown/""/bot) + text-based word overlap (60% threshold) + quality filter (3+ words, wake words exempt).
- **Interruption**: Bot stays in RESPONDING during playback, polls using actual PCM duration (`bytes / (sample_rate × 2)` for int16). Calls `stop_output_audio` on participant speech or stop phrases. Double-stop with 150 ms gap clears the MP3 queue.
- **Stop phrases close follow-up window**: `"thank you"`, `"thanks"`, `"stop"`, etc. kill audio AND clear `_last_response_time`.
- **Bot responses stored in buffer**: After answering, the bot's response is added to the transcript buffer so follow-up questions have full Q&A context.
- **Agent deletion cascades**: deletes documents (disk + ChromaDB embeddings), meetings, summaries, usage records, overrides.
- **Scope isolation invariant**: `MeetingSession.meeting_id` MUST be a DB UUID, never a meeting URL. Two users sharing a meeting URL would otherwise share RAG metadata. Enforced by `bot_engine.join_meeting()` (auto-UUID) and verified by `tests/test_meeting_id_scope.py`.
- **ffmpeg required**: `main.py:check_ffmpeg_available()` probes at startup. In `ENVIRONMENT=production` a missing binary aborts boot. In dev it logs ERROR. `recall_client.pcm_to_mp3_b64()` ERROR-logs once per process if conversion fails at runtime.
- **PRs go to `CognaraWorld/Synth`** (upstream). Follow `CONTRIBUTING.md`.

## Security Architecture

- **Webhook auth**: Svix scheme (`whsec_` secret + HMAC-SHA256 over `{message_id}.{timestamp}.{body}`, versioned `v1,...` signatures, `hmac.compare_digest`); legacy `X-Webhook-Secret` fallback. 300 s replay window with nonce dedup.
- **CORS**: Configurable via `CORS_ORIGINS` (default `http://localhost:3000`).
- **WebSocket auth**: **Tickets preferred** — `POST /api/auth/ws-ticket` issues 60 s single-use `secrets.token_urlsafe(32)` tokens; client connects via `?ticket=`. Legacy `?token=` (raw JWT) accepted with deprecation warning. Fail-closed; IDOR check via `Meeting.user_id == authenticated`.
- **JWT**: HS256, 24h TTL, includes `jti` for future revocation. SECRET_KEY != default-blocker in production.
- **Credit operations**: atomic reserve + idempotent settlement across 3 billing paths.
- **Startup validation**: production mode blocks on missing secrets AND missing ffmpeg.
- **Startup orphan cleanup**: stops any Recall bots left running after restart.
- **Password policy**: min 8 chars, uppercase + lowercase + digit.
- **File uploads**: extension allowlist `{pdf, docx, txt}`, magic-byte validation (`%PDF`, `PK`), 50 MB cap, path-traversal guard via `build_agent_upload_path`.
- **Security headers**: `X-Content-Type-Options=nosniff`, `X-Frame-Options=DENY`, `Referrer-Policy=strict-origin-when-cross-origin`, `Permissions-Policy` blocks camera/mic/geo, CSP `default-src 'none'; frame-ancestors 'none'`, HSTS `max-age=63072000; includeSubDomains` in production only.
- **Rate limits**: login 5/15min, register 3/h, service-token 5/min, create-checkout 10/h, create-meeting 5/min, chat 20/60s.

## Concurrency Model

- **Webhook semaphore**: `asyncio.Semaphore(50)` bounds concurrent transcription handlers.
- **Per-session processing lock**: `asyncio.Lock` per session prevents concurrent question handling.
- **Double-checked model init**: `_lazy_load_models()` with `asyncio.Lock`.
- **TTS lock**: `_tts_lock` serializes voice switching + synthesis in thread executor.
- **Session tracking**: `_ensure_session_tracking()` from ALL creation paths.
- **Thread-safe memory**: `_state_lock` protects entities/summaries across event loop and thread executor. `RollingSummary`, `RawTranscriptBuffer`, `RAGPipeline` all locked.
- **Shared embedding model**: module-level `_encode_lock` serializes ALL `SentenceTransformer.encode()` calls (model is not thread-safe).
- **No nested locks**: all acquisitions sequential.
- **Deque overflow protection**: evicted entries routed to embed buffer.

## Memory Architecture

```
Layer 1: Raw Buffer (10 min verbatim, deque maxlen=400, speaker grouping)
    ↓ overflow/age eviction
Layer 2: Embed Buffer → ChromaDB (200-word chunks, 10% overlap, scope metadata, cosine search)
    ↑ also receives document chunks (with document_id, agent_id, user_id)
Layer 3: Rolling Summary (hierarchical: prose + anchored key facts list, capped at 20)
Layer 4: Entity Tracker (people, decisions, action items — keyword markers, persisted on meeting end)
Layer 5: Past Meeting Summaries (cross-meeting memory from DB, last 3, loaded on startup + recovery)
Layer 6: Query Rewriting (expands ALL <10-word questions with last 3 speakers + topic words)
Layer 7: Bot Response Injection (bot's own answers added to buffer for follow-up context)

Scope Isolation:
- Every chunk tagged with meeting_id (DB UUID), agent_id, user_id, source_type
- Separate hybrid queries: current-meeting transcript (filter meeting_id), archived transcript (source_type), documents (source_type)
- Legacy metadata fallback (source: "document" | source: "meeting_transcript")
- Document deletion removes embeddings via delete_by_metadata()
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
      === DOCUMENT OVERVIEWS ===
      === LIVE CONTEXT (updates during meeting) ===
      === MEETING SUMMARY ===
      === TRACKED ENTITIES ===
      === RECENT CONVERSATION (last 10 minutes) ===
      === SHARED SCREEN CONTENT ===
      === PRIMARY SOURCE — use these first ===
      === WEB SEARCH RESULTS ===
```

Order is intentional: stable cacheable prefix (past meetings, documents) first; dynamic per-question content (recent buffer, RAG hits, web results) last. Optimized for Gemini implicit prompt caching.

## Recent Audit & Fix History

**2026-04-23 — End-to-end QA testing pass (six fixes shipped during live bot use)**:
- **Recall `/leave` URL was wrong** → bots stayed in meetings after "Leave" clicked. `recall_client.stop_bot` now uses `POST /bot/{id}/leave_call/`. Test: `tests/test_recall_leave_url.py`.
- **Recall `/stop_output_audio` URL was wrong** → "Stop" button was a no-op. `recall_client.stop_audio` now uses `DELETE /bot/{id}/output_audio/`. Test: `tests/test_recall_stop_audio_url.py`.
- **Document delete button was decorative** → no `onClick`. Added handler + `frontend/app/api/documents/[id]/route.ts` proxy. Backend cascade (file → ChromaDB chunks → DB row) was already correct.
- **`live_control._utcnow()` returned tz-aware UTC** → asyncpg DataError on every transcript webhook → UI feed froze. Fix returns naive UTC. Test: `tests/test_live_control_utcnow_naive.py`.
- **Bot only said filler then went silent** → abort path didn't reset `_interrupted` / `output_stop_requested`, every subsequent question bailed at the early-cancel check. Fix resets per-question flags at start of `_handle_question` and in the abort branch (preserves sticky `session_end_requested`). Test: `tests/test_filler_only_regression.py`.
- **Chat "Meeting not found" 404 for owner** → SQLAlchemy collection joinedload requires `.unique()`; old `try/except` exhausted the Result before retry. Fix calls `.unique()` upfront. Test: `tests/test_chat_meeting_lookup.py`.
- **Wake word phonetic variants expanded** for Deepgram mishearings. Bare-allowed: `nova, no va, nora, noah, mova, nove, noma, knowva`. Prefix-required (need wake prefix to disambiguate from "I'm in over my head"): `inn?\s*over, in nova, know va, no over, an over, the nova`. Test: `tests/test_wake_word_nova_variants.py`.
- Test suite: **378 passed**, 11 deselected (was 354 → +24 new tests across the 8 new test files).

**2026-04-23 — End-to-end simulation audit + remediation (earlier same day)**:
- Sample 15-utterance meeting traced through every subsystem by 4 specialist agents.
- **Fixed P0**: `MeetingSession.meeting_id` was being set to the meeting URL. Now propagates DB `Meeting.id` (UUID) end-to-end. Test: `tests/test_meeting_id_scope.py`.
- **Fixed P1**: `pcm_to_mp3_b64` swallowed `FileNotFoundError` from missing ffmpeg silently. Added `main.py:check_ffmpeg_available()` startup probe + ERROR log with one-shot flag. Test: `tests/test_ffmpeg_startup.py`.
- Documentation drift corrected: webhook semaphore 50 (not 20), 24 fillers across 6 categories (not 7), context budget split 10/15/25/10/20/20 (not 10/15/25/20/30), four wake-word families (not just nova).

## PR Status (recent)

- **#69** — merged: audit remediation for doc refusal and voice overlap in live meetings
- **#63** — merged: backend audit follow-up
- **#61** — merged: audit remediation (security, quality, tests, CI)
- **#60** — merged: backend meeting bot QA hardening
- **#55** — merged: chatbot reliability fixes
- **#53/#54** — merged: search default-yes routing + latency tuning
- **#50** — merged: 6 bug fixes across context/memory system
- **#42** — open / blocked: screenshare capture pipeline. `video_separate_png.data` is rejected by current Recall.ai API; transcript-only mode in production.

## Current State

Phase 10+ complete. Production-shaped architecture with idempotent billing across three settlement paths, scope-isolated RAG with shared embedding singleton, double-stop interrupts, sentence-level streaming, persona-bound voices, ticket-based WebSocket auth, Svix HMAC webhook validation, and ffmpeg startup probe. Latest QA pass (2026-04-23) shipped 6 user-visible fixes (Recall URL bugs, document delete, transcript feed timezone, filler-only loop, chat 404, wake word variants). Screen-share OCR pipeline still gated behind PR #42.
