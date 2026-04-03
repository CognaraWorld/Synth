# Synth — AI Meeting Participant Bot — Implementation Plan

## Context

Cognara World is building **Synth**, an AI-powered meeting bot that joins Zoom/Teams/Google Meet as an active voice participant. Unlike existing tools (Hedy AI, Vibe Bot, Zoom Companion) that do passive transcription or whisper-mode coaching, Synth speaks out loud in meetings — always on mute by default, raises hand before answering, and goes back on mute. It answers questions when invoked by name ("Hey Synth"), reads uploaded docs, searches the web live, and watches screen shares.

**Repo:** https://github.com/CongaraWorld/Synth
**Infra:** Mac Studio M4 Max 32GB (dev + early production)
**Stack:** Next.js (App Router) frontend + Python (FastAPI) backend

## Tech Stack Summary

| Layer | Technology | Local/Paid |
|---|---|---|
| Frontend (Dashboard) | Next.js 15 (App Router), Tailwind, shadcn/ui | Local |
| Backend (API + Bot Engine) | Python 3.12, FastAPI, WebSockets | Local |
| VAD | Silero VAD (~2MB, MIT) | Local, $0 |
| STT | Whisper Large-v3 Turbo via whisper.cpp/MLX | Local, $0 |
| LLM | Claude Haiku 4.5 (single model, streaming) | Paid API |
| TTS | Kokoro (82M params, Apache 2.0, am_michael voice) | Local, $0 |
| Web Search | Serper (primary) + SearXNG (fallback) | Serper paid, SearXNG local |
| Embeddings | all-MiniLM-L6-v2 (sentence-transformers) | Local, $0 |
| Vector DB | ChromaDB (in-memory per session) | Local, $0 |
| Meeting Infra | Recall.ai API | Paid, $0.65/hr |
| Database | PostgreSQL (local) | Local, $0 |
| Auth | NextAuth.js (Google OAuth + email) | Local, $0 |
| PDF Generation | Puppeteer | Local, $0 |
| Word Generation | python-docx | Local, $0 |
| File Storage | Local filesystem (MVP) → Cloudflare R2 (scale) | Local, $0 |

## Project Structure

```
Synth/
├── frontend/                    # Next.js App Router
│   ├── app/
│   │   ├── layout.tsx
│   │   ├── page.tsx             # Landing/login
│   │   ├── dashboard/
│   │   │   ├── page.tsx         # Main dashboard
│   │   │   ├── agents/
│   │   │   │   ├── new/page.tsx # Create new agent
│   │   │   │   └── [id]/page.tsx # Agent detail/session
│   │   │   ├── meetings/
│   │   │   │   ├── page.tsx     # Meeting history
│   │   │   │   └── [id]/page.tsx # Meeting detail + summary
│   │   │   └── settings/page.tsx
│   │   └── api/auth/            # NextAuth routes
│   ├── components/
│   │   ├── ui/                  # shadcn/ui components
│   │   ├── dashboard/           # Dashboard-specific components
│   │   ├── agent/               # Agent creation/management
│   │   └── meeting/             # Meeting views, live status
│   ├── lib/
│   │   ├── api.ts               # FastAPI client
│   │   └── auth.ts              # Auth config
│   ├── tailwind.config.ts
│   ├── next.config.ts
│   └── package.json
│
├── backend/                     # Python FastAPI
│   ├── app/
│   │   ├── main.py              # FastAPI app entry
│   │   ├── config.py            # Settings, env vars
│   │   ├── api/
│   │   │   ├── routes/
│   │   │   │   │   ├── agents.py    # CRUD for agents
│   │   │   │   ├── meetings.py  # Meeting management
│   │   │   │   ├── documents.py # File upload/parse
│   │   │   │   ├── webhook.py   # Recall.ai webhook receiver
│   │   │   │   └── auth.py      # Auth verification
│   │   │   └── websocket.py     # Live meeting status WS
│   │   ├── core/
│   │   │   ├── bot_engine.py    # Main meeting bot orchestrator
│   │   │   ├── vad.py           # Silero VAD wrapper
│   │   │   ├── stt.py           # Whisper wrapper
│   │   │   ├── tts.py           # Kokoro wrapper
│   │   │   ├── llm.py           # Claude Haiku 4.5 client (streaming)
│   │   │   ├── search.py        # Serper + SearXNG search client
│   │   │   ├── insight_detector.py # Passive fact-checking system
│   │   │   └── vision.py        # Screen share OCR via Claude
│   │   ├── context/
│   │   │   ├── manager.py       # Three-layer context orchestrator
│   │   │   ├── rolling_summary.py
│   │   │   ├── rag.py           # ChromaDB + embeddings
│   │   │   ├── raw_buffer.py    # Recent transcript buffer
│   │   │   └── documents.py     # Document parsing + chunking
│   │   ├── meeting/
│   │   │   ├── recall_client.py # Recall.ai API integration
│   │   │   ├── session.py       # Meeting session state
│   │   │   └── summary.py       # Post-meeting summary generation
│   │   ├── models/
│   │   │   ├── database.py      # SQLAlchemy models
│   │   │   └── schemas.py       # Pydantic schemas
│   │   └── utils/
│   │       ├── prompt_builder.py # System prompt from description
│   │       ├── wake_word.py     # "Hey Assistant" detection (14 phonetic variants)
│   │       ├── query_router.py  # Query classifier (6 categories) + web search router
│   │       └── filler.py        # Context-aware filler phrases (25 across 6 categories)
│   ├── requirements.txt
│   └── Dockerfile
│
├── docs/                        # Internal documentation
├── .env.example                 # Environment variable template
├── docker-compose.yml           # Local dev (Postgres, SearXNG)
└── README.md
```

## Implementation Phases

### Phase 1: Project Setup + Foundation (Days 1-3)

**Goal:** Repo scaffolding, local dev environment, database, auth.

- [ ] Clone repo, set up monorepo structure (`frontend/` + `backend/`)
- [ ] **Frontend:** Initialize Next.js 15 with App Router, Tailwind, shadcn/ui
- [ ] **Backend:** Initialize FastAPI project, set up config/env management
- [ ] **Database:** Set up local PostgreSQL, define SQLAlchemy models:
  - `users` (id, email, name, credits, created_at)
  - `agents` (id, user_id, name, description, system_prompt, mode, created_at)
  - `meetings` (id, agent_id, user_id, platform, meeting_link, status, started_at, ended_at)
  - `documents` (id, agent_id, filename, file_path, parsed, created_at)
  - `meeting_summaries` (id, meeting_id, content, pdf_path, docx_path, created_at)
- [ ] **Auth:** NextAuth.js with Google OAuth + email/password
- [ ] **Docker Compose:** Postgres + SearXNG containers for local dev
- [ ] Verify: Dashboard loads, user can sign up/login, DB migrations work

### Phase 2: Dashboard UI (Days 4-7)

**Goal:** Working dashboard where users can create agents and manage meetings.

- [ ] **Dashboard layout:** Sidebar nav, header, main content area
- [ ] **Agent creation flow:**
  - Form: agent name, description textarea, mode toggle (General/Custom)
  - On submit → backend generates tailored system prompt from description via Haiku
  - Display generated prompt, allow user to edit/confirm
- [ ] **Document upload:**
  - Drag-and-drop file upload (PDF, Word, TXT)
  - Show upload status, file list per agent
  - Backend: parse files → chunk → embed into ChromaDB (pre-meeting)
- [ ] **Meeting start flow:**
  - Input field for meeting link/ID
  - Platform auto-detection (Zoom/Teams/Meet from URL pattern)
  - "Join Meeting" button → calls backend → bot joins
- [ ] **Meeting history:** List of past meetings with status, duration, summary links
- [ ] **Meeting detail:** Transcript view, summary download (PDF/Word)
- [ ] Verify: Can create agent, upload docs, enter meeting link, view history

### Phase 3: AI Pipeline — VAD + STT + Wake Word (Days 8-12)

**Goal:** Audio comes in, gets filtered by VAD, transcribed by Whisper, wake word detected.

- [ ] **Silero VAD wrapper** (`core/vad.py`):
  - Load Silero VAD model (~2MB)
  - Process audio frames (~1-2ms per frame)
  - Output: speech_start, speech_end events
  - Configure sensitivity threshold for meeting environments
- [ ] **Whisper STT wrapper** (`core/stt.py`):
  - Load Whisper Large-v3 Turbo via whisper.cpp or MLX
  - Only processes audio segments where VAD detected speech
  - Returns: text, timestamp, confidence
  - Handles: chunked processing (2-3s segments)
- [ ] **Wake word detection** (`utils/wake_word.py`):
  - Detect "Hey Synth" in transcribed text
  - Extract the question that follows the wake word
  - Handle variations: "Hey Synth", "Synth", "Hey synth"
- [ ] **Transcript buffer** (`context/raw_buffer.py`):
  - Append transcribed text in real-time
  - Maintain sliding window of last 5-10 minutes
  - Thread-safe (multiple concurrent writes from STT)
- [ ] **Filler responses** (`utils/filler.py`):
  - Pre-generated audio files: "Let me check that...", "Good question...", etc.
  - Triggered immediately on wake word detection while LLM processes
- [ ] Verify: Feed test audio → VAD filters silence → Whisper transcribes → wake word triggers → filler plays

### Phase 4: Context Management — RAG + Rolling Summary (Days 13-17)

**Goal:** Three-layer context system working end-to-end.

- [ ] **Embedding pipeline** (`context/rag.py`):
  - Load all-MiniLM-L6-v2 locally
  - Background worker: every 30-60s, chunk transcript buffer
  - Chunk triggers: VAD speech-end, speaker change, 30s timeout, 3s silence
  - Embed chunks → store in ChromaDB with metadata (speaker, timestamp, index)
  - Retrieval: embed query → top 3 similar chunks → return with metadata
- [ ] **Rolling summary** (`context/rolling_summary.py`):
  - Background worker: every 5 minutes
  - Send new transcript chunk to Haiku: "Update this summary with new information"
  - Maintain compressed summary of entire meeting (~1,500-2,000 tokens)
- [ ] **Document processing** (`context/documents.py`):
  - PDF parsing (PyPDF2 or pdfplumber)
  - Word parsing (python-docx)
  - Chunk documents (~200-300 words per chunk)
  - Embed and store in same ChromaDB collection as transcript
- [ ] **Context manager** (`context/manager.py`):
  - Assembles context for each query:
    1. System prompt (agent persona)
    2. Rolling summary
    3. Recent raw buffer (last 5-10 min)
    4. RAG chunks (relevant to query)
    5. Document chunks (if relevant)
    6. Screen context (if available)
    7. User question
  - Enforces token budget (~5,000-10,000 per query)
- [ ] Verify: Upload a doc, start mock meeting, ask questions about doc content + past conversation. Context manager returns relevant chunks.

### Phase 5: LLM + Web Search + Voice Response (Days 18-22)

**Goal:** Bot receives question, gets smart answer, speaks it.

- [ ] **LLM client** (`core/llm.py`):
  - Claude API integration (Anthropic SDK)
  - Haiku 4.5 for simple queries
  - Sonnet 4.6 for complex reasoning
- [ ] **Query router** (`utils/query_router.py`):
  - Small Haiku call classifies: simple vs complex
  - Routes to appropriate model
  - Simple: factual lookups, time queries, straightforward answers
  - Complex: analysis, summarization, multi-step reasoning
- [ ] **Web search** (`core/search.py`):
  - SearXNG client (HTTP to local instance)
  - LLM decides if web search needed based on question
  - Parse results → inject into context → second LLM call with results
- [ ] **Screen share OCR** (`core/vision.py`):
  - Periodic screenshot of screen share (via Recall.ai)
  - Send to Claude Haiku vision for OCR
  - Store latest screen context, include in queries when relevant
- [ ] **TTS — Kokoro** (`core/tts.py`):
  - Load Kokoro model locally
  - Convert LLM text response → audio
  - Stream audio output
- [ ] **Prompt builder** (`utils/prompt_builder.py`):
  - Takes user's agent description
  - Generates tailored system prompt via Haiku
  - General mode: default helpful meeting assistant prompt
  - Custom mode: persona-specific prompt from description
- [ ] Verify: Ask "Hey Synth" a question → correct model routes → answer generated → audio response plays

### Phase 6: Recall.ai Integration — Bot Joins Meetings (Days 23-28)

**Goal:** Bot actually joins Zoom/Teams/Meet, listens, and speaks.

- [ ] **Recall.ai client** (`meeting/recall_client.py`):
  - Create bot → join meeting by link
  - Receive real-time audio stream
  - Send audio output (bot speaking)
  - Raise hand action
  - Mute/unmute actions
  - Screen share screenshot capture
- [ ] **Meeting session** (`meeting/session.py`):
  - State machine: JOINING → LISTENING → RESPONDING → LISTENING → ENDED
  - Orchestrates: audio in → VAD → STT → wake word → context → LLM → TTS → audio out
  - Handles: raise hand before speaking, auto-mute after speaking
  - Background tasks: rolling summary, RAG embedding, screen capture
- [ ] **Bot engine** (`core/bot_engine.py`):
  - Main orchestrator that ties everything together
  - Manages concurrent meeting sessions
  - Handles errors/reconnection gracefully
- [ ] **Live status WebSocket** (`api/websocket.py`):
  - Stream meeting status to dashboard: joined, listening, speaking, ended
  - Stream live transcript to dashboard
- [ ] Verify: Enter a real Zoom/Teams/Meet link → bot joins → listens → responds to "Hey Synth" → raises hand → speaks → mutes

### Phase 7: Post-Meeting Deliverables (Days 29-31)

**Goal:** Meeting ends, summary generated, PDF/Word delivered.

- [ ] **Summary generator** (`meeting/summary.py`):
  - On meeting end: send full transcript to Sonnet
  - Generate structured summary: key points, decisions, action items, Q&A
  - Store in database
- [ ] **PDF generation:**
  - Branded HTML template (logo, colors, layout)
  - Puppeteer renders → PDF
  - Store file, link to meeting record
- [ ] **Word generation:**
  - python-docx generates .docx from same structured content
  - Store file, link to meeting record
- [ ] **Email delivery:**
  - Send email to user with summary + download links
  - Use Resend or SMTP
- [ ] **Dashboard integration:**
  - Meeting detail page shows summary
  - Download buttons for PDF/Word
  - Transcript viewer
- [ ] Verify: Meeting ends → summary appears on dashboard within 2 minutes → PDF/Word download works → email received

### Phase 8: Polish + Credits System (Days 32-35)

**Goal:** Production-ready UX, credit-based payments.

- [ ] **Credit system:**
  - Users start with X free credits
  - 1 credit = 1 meeting
  - Track credits in database, deduct on meeting start
  - Block meeting start if no credits
- [ ] **Payment integration:**
  - Stripe Checkout for credit packs ($30/5, $100/20, $200/50)
  - Stripe webhook to add credits on payment
  - Billing history page
- [ ] **Dashboard polish:**
  - Loading states, error handling, empty states
  - Responsive design
  - Settings page (account, billing, notification preferences)
- [ ] **Error handling:**
  - Bot fails to join → notify user, refund credit
  - Meeting platform kicks bot → graceful handling
  - API errors → retry logic with backoff
- [ ] Verify: Purchase credits → start meeting → credit deducted → meeting works end-to-end

## Verification Plan

After each phase, verify:
1. **Phase 1:** `docker-compose up` → Postgres + SearXNG running → dashboard loads → auth works
2. **Phase 2:** Create agent → upload doc → enter meeting link → history page shows data
3. **Phase 3:** Feed audio file → VAD filters → Whisper transcribes → "Hey Synth" detected
4. **Phase 4:** Ask about uploaded doc → relevant chunks returned → rolling summary updates
5. **Phase 5:** Question → routed to correct model → answer with web search if needed → audio output
6. **Phase 6:** Real meeting link → bot joins → full loop works live
7. **Phase 7:** Meeting ends → summary + PDF/Word in <2 min → email sent
8. **Phase 8:** Buy credits → full flow → credits deducted correctly

## End-to-End Smoke Test

```
1. Sign up / login
2. Create agent: "Senior tech analyst, helpful and concise" (Custom mode)
3. Upload: quarterly_report.pdf
4. Paste: Zoom meeting link
5. Bot joins as "Synth"
6. During meeting: "Hey Synth, what does the report say about Q3 revenue?"
7. Synth raises hand → "Based on the quarterly report, Q3 revenue was..."
8. "Hey Synth, what's Apple's current stock price?"
9. Synth raises hand → searches web → "Apple is currently trading at..."
10. Meeting ends
11. Dashboard shows summary, transcript
12. Download PDF + Word
13. Email received with summary
14. 1 credit deducted from account
```

## Critical Risks

| Risk | Mitigation |
|---|---|
| Recall.ai rate limits or API changes | Abstract behind interface, ready to swap to MeetingBot |
| Whisper hallucinations in noisy meetings | Silero VAD pre-filtering, confidence thresholds |
| Latency too high (>5s) | Filler responses, streaming TTS, pre-warm models |
| Wake word false positives | Require exact "Hey Synth" + confidence threshold |
| Mac Studio crashes during meeting | Auto-save transcript, reconnect logic, consider UPS |
| 32GB RAM exceeded with concurrent meetings | Limit to 3-4 concurrent, queue additional |
