# Voice AI Agent — Initialization File

Welcome! I'm an AI assistant specializing in the Georgian Voice AI Platform. This file documents my understanding of the project and guides my work.

---

## Project Overview

**Georgian Voice AI Platform** — A real-time voice conversation platform enabling natural spoken conversations in Georgian. Users speak Georgian, and the AI responds with spoken Georgian output.

### Core Pipeline
```
User (Browser/WebRTC) → LiveKit Cloud → Python Agent → WisprFlow STT → GPT-4o/Gemini → ElevenLabs/Google TTS → Spoken Response
```

### Tech Stack
| Layer | Technology |
|-------|------------|
| Frontend | React / Next.js (web/) |
| Backend | Python LiveKit Agents (agent/) |
| STT | WisprFlow (WebSocket/REST) or ElevenLabs Scribe v2 |
| LLM | OpenAI GPT-4o or Google Gemini |
| TTS | ElevenLabs Multilingual v2 or Google Gemini TTS |
| WebRTC | LiveKit Cloud |
| Database | PostgreSQL (via asyncpg) |

---

## Project Structure

```
voice-ai/
├── agent/                      # Python LiveKit agent
│   ├── agent.py               # Main entry point (VoiceAssistant, entrypoint, prewarm)
│   ├── wisprflow_stt.py       # WisprFlow STT integration (REST + WebSocket)
│   ├── db.py                  # PostgreSQL conversation logging (asyncpg)
│   ├── google-credentials.json # Google Cloud credentials (gitignored)
│   ├── pyproject.toml         # Python dependencies (uv-managed)
│   └── conversations.db       # SQLite fallback (gitignored)
│
├── web/                       # Next.js frontend
│   ├── app/
│   │   ├── page.tsx          # Main voice UI page
│   │   ├── layout.tsx        # Root layout
│   │   └── api/
│   │       └── token/
│   │           └── route.ts  # LiveKit JWT token endpoint
│   ├── components/
│   │   └── VoiceAgent.tsx     # LiveKit room + voice UI (main UI component)
│   ├── package.json
│   ├── tsconfig.json
│   └── next.config.ts
│
├── README.md                  # Setup instructions
├── PRD.md                     # Product Requirements Document
├── CLAUDE.md                  # Project guidance (this file)
└── AGENTS.md                  # Repository guidelines
```

---

## Key Components

### Agent (`agent/agent.py`)

**Main Classes/Functions:**
- `VoiceAssistant` — Custom Agent subclass with Georgian system prompt, handles STT node override for WisprFlow
- `prewarm(proc: JobProcess)` — Loads Silero VAD in worker processes
- `entrypoint(ctx: JobContext)` — Session setup with STT/LLM/TTS/VAD, conversation logging hooks

**System Prompt (Georgian):**
```
შენ ხარ მეგობრული და დამხმარე ხელოვნური ინტელექტის ასისტენტი, რომელიც ქართულად საუბრობს.

წესები:
- ყოველთვის უპასუხე ქართულად.
- პასუხები იყოს მოკლე: მაქსიმუმ 2-3 წინადადება.
- იყავი ბუნებრივი და საუბრის ტონით.
- პატიოსნად აღიარე შენი შეზღუდვები.
```

**Configuration (Environment Variables):**
| Variable | Description |
|----------|-------------|
| `LIVEKIT_URL` | LiveKit Cloud WebSocket URL |
| `LIVEKIT_API_KEY` | LiveKit API key |
| `LIVEKIT_API_SECRET` | LiveKit API secret |
| `OPENAI_API_KEY` | OpenAI API key (for GPT-4o + Whisper) |
| `ELEVEN_API_KEY` | ElevenLabs API key (for TTS) |
| `WISPRFLOW_API_KEY` | WisprFlow API key (for Georgian STT) |
| `STT_PROVIDER` | `elevenlabs` (default), `wisprflow`, or `openai` |
| `DATABASE_URL` | PostgreSQL connection string |
| `VAD_ACTIVATION_THRESHOLD` | VAD threshold (default: 0.65) |
| `VAD_MIN_SPEECH_DURATION` | Min speech duration in seconds (default: 0.2) |
| `VAD_MIN_SILENCE_DURATION` | Min silence duration in seconds (default: 0.6) |
| `GOOGLE_APPLICATION_CREDENTIALS` | Path to Google credentials JSON |
| `NOISE_CANCELLATION_MODULE` | LiveKit noise cancellation module ID |

### STT Adapter (`agent/wisprflow_stt.py`)

Two implementations:
1. **REST API** — `transcribe_with_wisprflow()` — Send complete audio after VAD
2. **WebSocket** — `WisprFlowWebSocketSTT` — Stream audio chunks for real-time partial transcripts

Key functions:
- `pcm_to_wav_base64()` — Convert raw PCM to base64-encoded WAV
- `WisprFlowWebSocketSTT.process()` — Async generator yielding SpeechEvents

### Database (`agent/db.py`)

- Uses `asyncpg` for PostgreSQL connection pooling
- Tables: `sessions` (session_id, started_at, ended_at, metadata), `messages` (id, session_id, role, text, created_at, latency_ms)
- Falls back gracefully if `DATABASE_URL` not set

### Web Frontend (`web/`)

**`web/components/VoiceAgent.tsx`:**
- Main UI component using LiveKit's `useVoiceAssistant()`, `useTrackTranscription()`, `useLocalParticipant()` hooks
- Voice button with states: idle, listening (pulsing), processing (loading), speaking (waveform)
- Chat transcript showing conversation history
- Mic level meter

**`web/app/api/token/route.ts`:**
- Generates LiveKit JWT tokens for browser clients

---

## Running the Project

### Prerequisites
- Python 3.10+
- Node.js 18+
- `uv` (Python package manager)
- API keys in `agent/.env.local` and `web/.env.local`

### Quick Start

```bash
# Terminal 1: Start the Agent
cd agent
uv sync                          # First time: install dependencies
uv run agent.py download-files   # First time: download VAD model
uv run agent.py dev              # Dev mode (connects to LiveKit Cloud)
# OR: uv run agent.py console    # Console mode (local mic/speaker)

# Terminal 2: Start the Frontend
cd web
npm install                      # First time: install dependencies
npm run dev                      # Dev server at http://localhost:3000
```

Open http://localhost:3000 → Click the mic button → Speak Georgian.

### Commands Summary

| Command | Description |
|---------|-------------|
| `cd agent && uv sync` | Install/update Python dependencies |
| `uv run agent.py download-files` | Download VAD model (first time) |
| `uv run agent.py console` | Run with local mic/speaker (no server) |
| `uv run agent.py dev` | Dev mode (LiveKit Cloud, hot-reload) |
| `uv run agent.py start` | Production mode (JSON logs) |
| `cd web && npm install` | Install Node dependencies |
| `npm run dev` | Dev server at localhost:3000 |
| `npm run build` | Production build |

---

## Architecture Patterns

### LiveKit Agent Pipeline
1. **Prewarm** — VAD model loaded in worker processes
2. **Entrypoint** — Session created when room dispatched
3. **STT** — Audio → Text (WisprFlow or ElevenLabs Scribe)
4. **LLM** — Text → Response (GPT-4o or Gemini)
5. **TTS** — Response → Audio (ElevenLabs or Google)
6. **Playback** — Audio → Browser via WebRTC

### Streaming-First Design
Every stage streams into the next in parallel:
- STT → LLM (streaming transcripts)
- LLM → TTS (sentence-level chunking)
- TTS → Playback (chunked audio)

### Conversation Logging
- Events: `user_input_transcribed`, `conversation_item_added`
- Async logging via `asyncio.create_task()` (non-blocking)
- Logs to PostgreSQL (or disabled if no DATABASE_URL)

---

## Key Implementation Details

### Custom WisprFlow STT Integration
The agent can use WisprFlow instead of ElevenLabs Scribe:
```bash
STT_PROVIDER=wisprflow uv run agent.py dev
```

WisprFlow requires:
- 16kHz mono PCM WAV input (LiveKit sends 48kHz Opus → resampled)
- API key in `WISPRFLOW_API_KEY`
- Language code `ka` (Georgian)

### VAD Tuning
The VAD is tuned to reject background office noise:
- `VAD_ACTIVATION_THRESHOLD = 0.65` (higher = more strict)
- `VAD_MIN_SPEECH_DURATION = 0.2s`
- `VAD_MIN_SILENCE_DURATION = 0.6s`

### Noise Cancellation
Optional LiveKit noise cancellation:
```bash
NOISE_CANCELLATION_MODULE=rnnoise uv run agent.py dev
```

---

## Coding Conventions

### Python
- **Style:** PEP 8, 4-space indent
- **Type hints:** Required on public functions
- **File naming:** `snake_case.py`
- **Class naming:** `PascalCase`
- **Async:** Use `async`/`await` throughout
- **Logging:** Use `logging.getLogger(__name__)`

### TypeScript/React
- **Components:** Functional with hooks
- **File naming:** `PascalCase.tsx` for components, `kebab-case.tsx` for routes
- **Directives:** `"use client"` for client components
- **Styles:** Inline styles (no CSS modules in this project)

### Git Commits
- Conventional Commits: `feat:`, `fix:`, `chore:`, `docs:`, `refactor:`, `test:`
- Example: `feat: add chat transcript view`

---

## Database Queries

```bash
# View conversation logs (PostgreSQL)
psql $DATABASE_URL -c "SELECT role, text, created_at FROM messages ORDER BY created_at"

# Or via SQLite (fallback, if using)
sqlite3 agent/conversations.db "SELECT role, text, datetime(created_at, 'unixepoch') FROM messages"
```

---

## Environment Files

Two separate `.env.local` files (both gitignored):

**`agent/.env.local`:**
```
LIVEKIT_URL=wss://...
LIVEKIT_API_KEY=...
LIVEKIT_API_SECRET=...
OPENAI_API_KEY=...
ELEVEN_API_KEY=...
WISPRFLOW_API_KEY=...
STT_PROVIDER=elevenlabs
DATABASE_URL=postgresql://...
GOOGLE_APPLICATION_CREDENTIALS=agent/google-credentials.json
```

**`web/.env.local`:**
```
LIVEKIT_URL=wss://...
LIVEKIT_API_KEY=...
LIVEKIT_API_SECRET=...
```

---

## What I Can Help With

As an AI agent working on this project, I can assist with:

1. **Code modifications** — Edit Python/TypeScript files, add features
2. **Debugging** — Analyze errors, fix bugs, optimize performance
3. **Testing** — Add unit tests, integration tests
4. **Documentation** — Update README, PRD, code comments
5. **Configuration** — Set up environment variables, deployment
6. **Architecture** — Refactor components, add new integrations
7. **Database** — Design schemas, write queries
8. **Frontend** — Enhance UI, add components
9. **DevOps** — Docker, deployment scripts, CI/CD

---

## How to Work With Me

To get the best results, provide:

1. **Clear task description** — What you want to accomplish
2. **Context** — Which files/components are relevant
3. **Constraints** — Any specific requirements or limitations
4. **Testing approach** — How you'll verify the solution works

I'll:
- Read relevant files before making changes
- Explain my approach before executing
- Report progress and issues
- Verify results when possible

---

## Important Notes

- **Credential files are gitignored** — Never commit secrets
- **Agent multiprocessing** — Logs from child processes don't appear in parent's stdout in `dev` mode
- **STT is swappable** — Via `STT_PROVIDER` env var
- **All UI text is in Georgian** — System prompt enforces Georgian responses
- **End-to-end latency target** — < 3 seconds (speech → response)
- **Conversation logs** — Stored in PostgreSQL (asyncpg) or SQLite fallback

---

*Last updated: February 2026*
*Project owner: Irakli*
*Version: MVP 0.3*
