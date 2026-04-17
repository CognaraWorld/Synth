# Synth

An AI-powered meeting bot that joins Zoom, Microsoft Teams, and Google Meet as an active voice participant.

## What It Does

Synth joins your meetings and participates like a real team member:

- **Voice participation** — Speaks out loud with synthesized voice when asked
- **Always polite** — Stays on mute by default, raises hand before speaking
- **Invoked by name** — Only responds when you say "Hey Synth"
- **Document-aware** — Reads uploaded PDFs, Word files, and watches screen shares
- **Web-grounded** — Searches the web live for up-to-date answers
- **Custom personas** — Configure the bot's role and expertise per session
- **Live operator controls** — Activate sessions, inspect transcript state, mute or unmute, and send typed steering instructions from the dashboard
- **Post-meeting summaries** — Generates PDF/Word reports with key points and action items

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | Next.js 15 (App Router), Tailwind CSS, shadcn/ui |
| Backend | Python 3.12, FastAPI, WebSockets |
| Voice Activity Detection | Silero VAD |
| Speech-to-Text | Whisper Large-v3 Turbo (local) |
| Text-to-Speech | Kokoro (local) |
| LLM | Claude Haiku 4.5 |
| Web Search | SearXNG (self-hosted) |
| Embeddings | all-MiniLM-L6-v2 (local) |
| Vector DB | ChromaDB (in-memory) |
| Meeting Infra | Recall.ai API |
| Database | PostgreSQL |

## Getting Started

### Prerequisites

- Python 3.12+ (3.11+ works locally; CI uses 3.12)
- Node.js 22+
- Docker & Docker Compose
- PostgreSQL (or use Docker)
- **ffmpeg** on the server that runs the backend — required for Recall.ai bot audio (PCM→MP3 via pydub) and some export paths. Install with `apt install ffmpeg`, `brew install ffmpeg`, or ship it in your container image.

### Meeting latency metrics (optional)

- In-process **p50 / p95** rollups for Q&A stage gaps are recorded automatically; every 50 completed turns the backend logs a compact JSON line: `meeting_latency_rollup {...}`.
- **GET `/api/health/meeting-latency`** returns the current snapshot when `ENVIRONMENT=development`, or in production when **`EXPOSE_MEETING_LATENCY_METRICS=true`** (maps to `expose_meeting_latency_metrics` in `Settings`).
- **GET `/metrics`** exposes Prometheus metrics when `prometheus-fastapi-instrumentator` is installed.

### Setup

```bash
# Clone the repo
git clone https://github.com/CongaraWorld/Synth.git
cd Synth

# Copy environment config
cp .env.example .env
# Edit .env with your API keys

# Start Postgres + SearXNG
docker-compose up -d

# Optional: run the backend in Docker too
docker-compose --profile backend up -d backend

# Backend
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# Frontend (new terminal)
cd frontend
npm install
npm run dev
```

### Environment Variables

See `.env.example` for all required configuration. At minimum you need:

- `ANTHROPIC_API_KEY` — Claude API access
- `RECALL_API_KEY` — Recall.ai for meeting bot infrastructure
- `DATABASE_URL` — PostgreSQL connection string

## Project Structure

```
Synth/
├── frontend/          # Next.js dashboard
├── backend/           # FastAPI + AI pipeline
│   ├── app/
│   │   ├── api/       # REST endpoints
│   │   ├── core/      # VAD, STT, TTS, LLM, search
│   │   ├── context/   # RAG, rolling summary, buffer
│   │   ├── meeting/   # Recall.ai, session management
│   │   ├── models/    # Database models + schemas
│   │   └── utils/     # Wake word, routing, prompts
├── docs/              # Documentation
└── docker-compose.yml # Postgres + SearXNG, optional backend profile
```

## License

Private — All rights reserved.
