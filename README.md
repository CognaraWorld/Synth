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
- **Post-meeting summaries** — Generates PDF/Word reports with key points and action items

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | Next.js 15 (App Router), Tailwind CSS, shadcn/ui |
| Backend | Python 3.12, FastAPI, WebSockets |
| Voice Activity Detection | Silero VAD |
| Speech-to-Text | Whisper Large-v3 Turbo (local) |
| Text-to-Speech | Kokoro (local) |
| LLM | Claude Haiku 4.5 + Sonnet 4.6 (hybrid routing) |
| Web Search | SearXNG (self-hosted) |
| Embeddings | all-MiniLM-L6-v2 (local) |
| Vector DB | ChromaDB (in-memory) |
| Meeting Infra | Recall.ai API |
| Database | PostgreSQL |

## Getting Started

### Prerequisites

- Python 3.12+
- Node.js 22+
- Docker & Docker Compose
- PostgreSQL (or use Docker)

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
└── docker-compose.yml # Postgres + SearXNG
```

## License

Private — All rights reserved.
