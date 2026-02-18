# Georgian Voice AI Platform

Real-time Georgian voice conversation platform. Speak Georgian, get spoken responses from AI.

**Pipeline:** User speaks → WisprFlow STT → GPT-4o → ElevenLabs TTS → spoken response

Orchestrated by LiveKit Agents Framework with a React/Next.js frontend.

## Architecture

```
Browser (React + LiveKit Client SDK)
  │
  ├─ [WebRTC audio] ──→ LiveKit Cloud
  │                        │
  │                        └─→ Python Agent
  │                              ├─→ WisprFlow (STT)
  │                              ├─→ GPT-4o (LLM)
  │                              └─→ ElevenLabs (TTS)
  │
  └─ [WebRTC audio] ←── LiveKit Cloud ←── TTS audio
```

## Prerequisites

- Python 3.10+
- Node.js 18+
- [uv](https://docs.astral.sh/uv/) (Python package manager)
- API keys configured in `agent/.env.local` and `web/.env.local`

## Quick Start

### 1. Start the Agent

```bash
cd agent

# Install dependencies (first time)
uv sync

# Download VAD model (first time)
uv run agent.py download-files

# Run in console mode (local mic/speaker, no server)
uv run agent.py console

# Or run in dev mode (connects to LiveKit Cloud)
uv run agent.py dev
```

### 2. Start the Frontend

```bash
cd web

# Install dependencies (first time)
npm install

# Run dev server
npm run dev
```

Open http://localhost:3000 → click the mic button → speak Georgian.

## STT Provider

By default, OpenAI Whisper is used for STT. To use WisprFlow:

```bash
STT_PROVIDER=wisprflow uv run agent.py dev
```

Set `STT_PROVIDER` in `agent/.env.local` to persist the choice.

## Configuration

### agent/.env.local

| Variable | Description |
|----------|-------------|
| `LIVEKIT_URL` | LiveKit Cloud WebSocket URL |
| `LIVEKIT_API_KEY` | LiveKit API key |
| `LIVEKIT_API_SECRET` | LiveKit API secret |
| `OPENAI_API_KEY` | OpenAI API key (for GPT-4o + Whisper) |
| `ELEVEN_API_KEY` | ElevenLabs API key (for TTS) |
| `WISPRFLOW_API_KEY` | WisprFlow API key (for Georgian STT) |
| `STT_PROVIDER` | `openai` (default) or `wisprflow` |

### web/.env.local

| Variable | Description |
|----------|-------------|
| `LIVEKIT_URL` | LiveKit Cloud WebSocket URL |
| `LIVEKIT_API_KEY` | LiveKit API key |
| `LIVEKIT_API_SECRET` | LiveKit API secret |

## Project Structure

```
Voice AI/
├── agent/                    # Python LiveKit agent
│   ├── agent.py              # Main entrypoint
│   ├── wisprflow_stt.py      # WisprFlow STT integration
│   ├── db.py                 # SQLite conversation logging
│   └── pyproject.toml        # Python dependencies
│
├── web/                      # React/Next.js frontend
│   ├── app/
│   │   ├── page.tsx          # Voice UI page
│   │   └── api/token/route.ts # LiveKit token endpoint
│   ├── components/
│   │   └── VoiceAgent.tsx    # LiveKit room + voice UI
│   └── package.json
│
├── PRD.md                    # Product Requirements Document
└── README.md                 # This file
```

## Conversation Logs

Conversations are logged to `agent/conversations.db` (SQLite). Query with:

```bash
sqlite3 agent/conversations.db "SELECT role, text, datetime(created_at, 'unixepoch') FROM messages ORDER BY created_at"
```
