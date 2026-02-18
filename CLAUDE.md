# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Georgian Voice AI — a real-time voice conversation platform. Users speak Georgian, get spoken responses from AI. Built with LiveKit Agents Framework (Python) + React/Next.js frontend.

## Commands

### Agent (Python, in `agent/`)
```bash
uv sync                        # Install/update dependencies
uv run agent.py download-files # Download VAD model (first time)
uv run agent.py dev            # Dev mode (connects to LiveKit Cloud, hot-reload)
uv run agent.py console        # Console mode (local mic/speaker, no server)
uv run agent.py start          # Production mode (JSON logs, multi-process)
```

### Web (Next.js, in `web/`)
```bash
npm install      # Install dependencies
npm run dev      # Dev server at http://localhost:3000
npm run build    # Production build
```

### Both must run simultaneously for local development.

### Database
```bash
sqlite3 agent/conversations.db "SELECT role, text, datetime(created_at, 'unixepoch') FROM messages ORDER BY created_at"
```

## Architecture

```
Browser (React/Next.js) → POST /api/token → LiveKit JWT
  ↕ WebRTC audio via LiveKit Cloud
Python Agent (agent.py)
  ├─ STT: ElevenLabs Scribe v2 (Georgian, ka)
  ├─ LLM: OpenAI GPT-4o
  ├─ TTS: Google Cloud Chirp 3 (ka-GE)
  ├─ VAD: Silero (tunable via env vars)
  └─ Turn Detection: Multilingual model
  └─ Logging: SQLite (conversations.db)
```

- **agent/agent.py**: Entry point. Defines `VoiceAssistant` (extends LiveKit `Agent`), prewarm (VAD loading), and `entrypoint` (session setup with STT/LLM/TTS/VAD). Hooks into session events for conversation logging.
- **agent/db.py**: Async SQLite wrapper (`aiosqlite`) with `sessions` and `messages` tables.
- **agent/wisprflow_stt.py**: Custom STT adapter for WisprFlow API (WebSocket streaming, 16kHz resampling).
- **web/components/VoiceAgent.tsx**: Main UI component — connection flow, voice visualizer, mic level meter, chat transcript. Uses `useVoiceAssistant()`, `useTrackTranscription()`, `useLocalParticipant()` hooks.
- **web/app/api/token/route.ts**: Generates LiveKit JWT tokens for browser clients.

## Key Patterns

- Agent uses LiveKit's multiprocessing: `prewarm` runs in worker child processes, `entrypoint` runs when a room is dispatched. Logs from child processes don't appear in the parent's stdout in `dev` mode.
- STT provider is swappable via `STT_PROVIDER` env var (`elevenlabs`, `wisprflow`, `openai`).
- Google Cloud credentials are passed explicitly via `credentials_file` parameter (not just env var) because LiveKit's multiprocessing child processes may not inherit `GOOGLE_APPLICATION_CREDENTIALS`.
- VAD thresholds are tunable via `VAD_ACTIVATION_THRESHOLD`, `VAD_MIN_SPEECH_DURATION`, `VAD_MIN_SILENCE_DURATION` env vars.
- All UI text is in Georgian. System prompt instructs the LLM to always respond in Georgian.

## Environment Variables

Two separate `.env.local` files (both gitignored):
- **agent/.env.local**: `LIVEKIT_URL`, `LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET`, `OPENAI_API_KEY`, `ELEVEN_API_KEY`, `GOOGLE_APPLICATION_CREDENTIALS`, `STT_PROVIDER`
- **web/.env.local**: `LIVEKIT_URL`, `LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET`

## Coding Conventions

- **Python**: PEP 8, type hints on public functions, async/await throughout. Uses `uv` for package management.
- **TypeScript/React**: Functional components with hooks, inline styles (no CSS modules), `"use client"` directive for client components.
- **Commits**: Conventional Commits (`feat:`, `fix:`, `chore:`, `docs:`, `refactor:`).
- Credential files (`google-credentials.json`, `.env.local`) are gitignored — never commit secrets.
