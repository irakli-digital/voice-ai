# Product Requirements Document
## Georgian Voice AI — MVP Specification

| Field | Detail |
|-------|--------|
| **Product** | Georgian Voice AI Platform (Web MVP) |
| **Owner** | Irakli |
| **Version** | 0.3 — MVP Revised |
| **Date** | February 2026 |
| **Status** | Draft |
| **Target** | Georgian-language voice conversation platform |

---

## 1. Overview

A web-based voice AI platform that enables natural spoken conversations in Georgian. The user speaks, the system transcribes, generates an intelligent response, and speaks it back — creating a fluid, voice-first interaction. The platform is vertical-agnostic: the core MVP proves the voice pipeline works for Georgian, and specific use cases (appointment booking, customer support, etc.) are layered on top later.

All conversations are recorded and stored as structured chat logs for review and analytics.

## 2. Problem Statement

Georgian has limited support across mainstream voice AI platforms. There is no off-the-shelf solution that provides end-to-end voice conversation in Georgian with acceptable quality and latency. Existing tools are either English-only or produce poor results for Georgian speech recognition and synthesis. This platform fills that gap by combining best-available Georgian STT, a capable LLM, and multilingual TTS into a single real-time voice pipeline.

## 3. MVP Scope

### 3.1 What MVP Is

A working voice conversation loop in Georgian:
1. User speaks Georgian into a web interface
2. Speech is transcribed accurately
3. LLM generates a contextual Georgian response
4. Response is spoken back in natural-sounding Georgian
5. Conversation is logged for review

**The MVP proves the pipeline works.** Vertical-specific features (booking, support, Q&A) come after the core is solid.

### 3.2 User Experience

The interface is minimal and voice-first:

- A single large circular button dominates the screen
- Press to start listening — visual feedback shows active listening state (pulsing ring / waveform)
- Release or silence-detected — system processes and responds with synthesized speech
- Conversation history visible as a scrollable chat transcript below the button
- Each turn shows: user message (transcribed text) and AI response (generated text)

### 3.3 Core Flow

| Step | Action | Component | Target Latency |
|------|--------|-----------|----------------|
| 1 | User presses button and speaks | LiveKit Client SDK (WebRTC) | — |
| 2 | Audio streamed to server | LiveKit WebRTC transport | < 50ms |
| 3 | Speech-to-Text transcription | WisprFlow (streaming via WebSocket) | < 1.2s |
| 4 | LLM generates response | GPT-4o (streaming) | < 2s (first token) |
| 5 | Text-to-Speech synthesis | ElevenLabs Multilingual v2 | < 1s (first audio chunk) |
| 6 | Audio played back to user | LiveKit WebRTC transport | Immediate on chunk arrival |
| 7 | Conversation logged | Backend persistence | Async, non-blocking |

**End-to-End Latency Target: < 3 seconds**
From user finishing speech to first audio playback of AI response. This is the critical metric that determines whether the experience feels conversational or broken.

### 3.4 Error UX

- **STT fails or returns garbage:** AI responds with "ვერ გავიგე, გაიმეორეთ, თუ შეიძლება" ("I didn't understand, could you repeat?")
- **LLM timeout:** Visual indicator + fallback message "ერთი წუთით, ვფიქრობ..." ("One moment, I'm thinking...")
- **TTS fails:** Display text response in chat transcript (graceful degradation to text-only)
- **Connection drop:** LiveKit handles reconnection automatically; show "Reconnecting..." state

## 4. Technical Architecture

### 4.1 Pipeline Design — Streaming-First

**Critical principle:** Never wait for a full step to complete before starting the next. Every stage must stream into the next stage in parallel.

- **Audio Capture → STT (streaming):** LiveKit captures audio from the browser via WebRTC and routes it to WisprFlow through a custom STT plugin using WisprFlow's WebSocket API. Partial transcripts arrive in real-time.
- **STT → LLM (streaming):** Once the final transcript is confirmed (LiveKit's built-in VAD detects end-of-speech), it is immediately sent to GPT-4o with streaming enabled. Response tokens begin arriving within ~500ms.
- **LLM → TTS (streaming input):** LLM tokens are buffered into sentence-sized chunks and piped to ElevenLabs Multilingual v2 via LiveKit's native TTS plugin. TTS begins synthesizing audio from the first sentence while the LLM is still generating.
- **TTS → Playback (streaming):** Synthesized audio is routed back through LiveKit's WebRTC transport to the browser for immediate playback.

**Architecture Diagram**

```
Browser (React + LiveKit Client SDK)
  │
  ├─ [WebRTC audio] ──→ LiveKit Cloud (EU region)
  │                        │
  │                        └─→ LiveKit Agent (Python)
  │                              ├─→ WisprFlow WebSocket (STT, streaming)
  │                              ├─→ GPT-4o (LLM, streaming)
  │                              └─→ ElevenLabs Multilingual v2 (TTS)
  │                              │
  │                              └─→ PostgreSQL (conversation logs)
  │
  └─ [WebRTC audio] ←── LiveKit Cloud ←── TTS audio chunks
```

### 4.2 Component Stack

| Layer | Technology | Notes |
|-------|-----------|-------|
| Frontend | React / Next.js | Single-page app. LiveKit Client SDK handles all audio via WebRTC. |
| Backend Orchestrator | LiveKit Agents Framework (Python) | Handles audio routing, VAD, and STT → LLM → TTS orchestration. |
| STT | WisprFlow API | WebSocket streaming API. Georgian confirmed. Custom LiveKit STT plugin required. Input: 16kHz PCM wav (conversion from WebRTC audio needed). |
| LLM | OpenAI GPT-4o | Streaming mode. System prompt configures Georgian persona and conversation context. |
| TTS | ElevenLabs Multilingual v2 | Native LiveKit plugin available. Input streaming pipes LLM tokens directly. |
| Database | PostgreSQL | Conversation logs, session data. SQLite acceptable for early MVP. |
| Hosting | LiveKit Cloud | Already provisioned (`irakli-eo6guz14.livekit.cloud`). Check/move to EU region for lower latency to Georgian users. |

### 4.3 WisprFlow Integration Notes

WisprFlow is a dictation-focused STT service with some specifics to account for:

- **WebSocket API** for real-time streaming (preferred over REST for latency)
- **Warm-up API** available to pre-warm connections and reduce first-request latency
- **Input format:** 16kHz PCM wav (browser WebRTC uses Opus — need server-side transcoding in the LiveKit agent)
- **Auto-editing behavior:** WisprFlow cleans up dictation (removes fillers, reformats). For voice AI, monitor whether this helps or hurts accuracy. May need raw mode if available.
- **API access is gated** — requires approval from WisprFlow team. Already obtained (key in `.env`).

### 4.4 Voice Activity Detection (VAD)

LiveKit Agents framework includes built-in VAD powered by Silero:

- **Silero VAD** runs server-side within the LiveKit Agent. Detects end-of-speech with ~200ms accuracy. Configurable silence threshold and speech padding.
- **Tuning parameters:** `min_silence_duration` (default 500ms), `prefix_padding` (default 300ms), and `min_speech_duration` (default 100ms) — tune for Georgian speech patterns, which may have longer natural pauses between words.

## 5. Alternatives Evaluated

### 5.1 Platform Solutions

**Decision: LiveKit Agents Framework** (open-source, self-hostable via LiveKit Cloud).

- **Full control:** Open-source with no vendor lock-in.
- **Native plugin ecosystem:** First-party plugins for OpenAI, ElevenLabs, Silero VAD. Custom WisprFlow plugin built using the STT base class.
- **WebRTC transport:** Lower latency than WebSocket for audio. Built-in connectivity handling.
- **Pipeline abstraction:** `VoicePipelineAgent` handles the entire STT → LLM → TTS flow.

| Platform | Why Not Selected |
|----------|-----------------|
| Vapi.ai | Per-minute cost model. Less control over pipeline. Georgian support depends on their integrations. |
| Retell.ai | Vendor lock-in. Less flexibility for custom STT provider. |
| Daily.co + Pipecat | Strong alternative. Pipecat is newer with less documentation. Revisit if LiveKit doesn't work. |

### 5.2 STT Alternatives

| Provider | Georgian Quality | Streaming | Latency | Status |
|----------|-----------------|-----------|---------|--------|
| **WisprFlow** | Confirmed | Yes (WebSocket) | Fast | **SELECTED** |
| OpenAI Whisper API | Good | No (batch) | Medium | Fallback option |
| Deepgram | Improving | Yes | Very fast | Monitor |
| Google Cloud STT | Good | Yes | Fast | Benchmarked |

### 5.3 TTS Alternatives

| Provider | Georgian Quality | Streaming | Latency | Status |
|----------|-----------------|-----------|---------|--------|
| **ElevenLabs Multilingual v2** | Strong | Yes (input streaming) | Medium | **SELECTED** |
| OpenAI TTS | Decent | Yes | Fast | Fallback option |
| Google Cloud TTS | Good | Yes | Fast | Benchmarked |

> **Pre-build validation:** Record 10 Georgian audio samples, test WisprFlow accuracy. Generate 10 Georgian text samples through ElevenLabs and rate naturalness. Do this in Week 1 before committing to the full build.

## 6. Latency Strategy

### 6.1 Latency Budget

| Stage | Budget | Optimization |
|-------|--------|-------------|
| Audio capture → Server | < 50ms | WebRTC via LiveKit. Opus codec. |
| STT processing | < 1,200ms | WisprFlow WebSocket streaming. Pre-warmed connection. |
| STT → LLM handoff | < 30ms | VoicePipelineAgent internal handoff. |
| LLM first token | < 800ms | GPT-4o streaming. Concise system prompt. |
| LLM → TTS buffering | < 200ms | Sentence-level chunking. |
| TTS first audio chunk | < 700ms | ElevenLabs input streaming. |
| Audio delivery | < 50ms | WebRTC playback via LiveKit. |

**Total: ~2.0–3.0 seconds** (end-of-speech to first audio response)

### 6.2 Key Optimizations

- **Streaming everything:** VoicePipelineAgent manages the full pipeline. No custom glue code.
- **Sentence-level TTS:** Don't wait for full LLM response. Buffer tokens to sentence boundaries, send to ElevenLabs immediately.
- **Connection pre-warming:** WisprFlow warm-up API + LiveKit persistent connections to providers.
- **EU region deployment:** LiveKit Cloud in EU — closer to Georgian users (~40ms) while still reasonable to US-based APIs (~90ms). Net win over US-East.
- **Concise system prompt:** Shorter prompt = faster first token from GPT-4o.

## 7. Data Model

### 7.1 Conversation Storage

| Entity | Fields | Notes |
|--------|--------|-------|
| Session | `session_id`, `started_at`, `ended_at`, `status`, `metadata` | One per conversation |
| Message | `message_id`, `session_id`, `role` (user/assistant), `text`, `audio_url`, `created_at`, `latency_ms` | Each turn |
| AudioBlob | `blob_id`, `message_id`, `format`, `duration_ms`, `storage_path` | Local file storage for MVP. S3/GCS for production. |

### 7.2 What Gets Recorded

- User's original audio (raw recording)
- Transcribed text from WisprFlow
- LLM-generated response text
- Synthesized response audio (optional — can regenerate from text)
- Timestamps and latency metrics per turn
- Session metadata (device, browser, duration)

## 8. MVP Feature Set

### 8.1 In Scope (P0)

- Push-to-talk voice interaction with visual button
- Visual states: idle, listening (pulsing), processing (loading), speaking (waveform)
- Georgian speech-to-text via WisprFlow
- Contextual response generation via GPT-4o (Georgian)
- Text-to-speech response via ElevenLabs Multilingual v2
- Real-time audio transport via LiveKit (WebRTC)
- Scrollable chat transcript showing conversation history
- Conversation logging (text + audio) to PostgreSQL
- Error fallback UX (repeat request, text-only degradation)
- Sub-4-second end-to-end response latency

### 8.2 Deferred (Post-MVP)

- **Vertical-specific features** (appointment booking, customer support, Q&A — chosen after MVP)
- Hands-free mode (VAD-based, no button press)
- Interrupt handling / barge-in
- Multi-language switching (English + Georgian)
- Admin dashboard for conversation logs
- User authentication
- Custom voice cloning
- Mobile app

## 9. LLM System Prompt Strategy

The GPT-4o system prompt for the MVP general assistant:

- **Language:** Always respond in Georgian. If the user speaks another language, still respond in Georgian unless explicitly asked otherwise.
- **Persona:** Friendly, conversational, helpful. No specific brand voice for MVP.
- **Brevity:** 2–3 sentences max per response. Long responses destroy voice UX and inflate latency + TTS cost.
- **Context:** Include last 10 conversation turns for continuity.
- **Safety:** Standard guardrails. No harmful content. Acknowledge limitations honestly.
- **Voice-optimized:** Avoid bullet points, code, URLs, or anything that doesn't work in spoken form. Use natural sentence structure.

## 10. Cost Model

### 10.1 Estimated Per-Conversation Costs

Assuming ~5 turns per conversation, ~10 seconds of user speech per turn:

| Service | Unit Cost | Per Conversation | Notes |
|---------|----------|-----------------|-------|
| WisprFlow STT | TBD (gated pricing) | TBD | Contact WisprFlow for pricing. May be per-minute or per-request. |
| GPT-4o | ~$0.01 per turn | ~$0.05 | Short system prompt + 10 turns context window |
| ElevenLabs TTS | ~$0.05 per minute of audio | ~$0.10 | ~2 min total AI speech per conversation |
| LiveKit Cloud | Free tier / ~$0.01/min | ~$0.05 | Depends on plan |
| **Total** | | **~$0.20–0.30** | **Per 5-turn conversation** |

### 10.2 Monthly Budget ($100–500)

| Tier | Conversations/month | Notes |
|------|-------------------|-------|
| $100/mo | ~330–500 conversations | Development + light testing |
| $300/mo | ~1,000–1,500 conversations | Active internal use + demos |
| $500/mo | ~1,600–2,500 conversations | Early users / beta |

## 11. Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|-----------|
| Georgian STT accuracy is poor | High — breaks core UX | Benchmark WisprFlow in Week 1 with 10 samples. Fallback: OpenAI Whisper API. |
| Georgian TTS sounds unnatural | Medium — degrades experience | Test ElevenLabs with Georgian text samples. Fallback: Google Cloud TTS. |
| End-to-end latency > 4s | High — feels broken | Streaming-first architecture. Sentence-level TTS. Measure each stage independently. |
| WisprFlow WebSocket → LiveKit integration is complex | High — blocks pipeline | WisprFlow requires 16kHz PCM wav; LiveKit sends Opus. Need transcoding layer. Budget extra time in Week 1–2. |
| Solo developer + new to LiveKit/WebRTC | Medium — timeline risk | Add learning/prototyping week. Follow LiveKit's official voice agent examples closely. Don't over-customize. |
| WisprFlow auto-editing changes meaning | Medium — transcription drift | Test with Georgian names, dates, numbers. If auto-edit hurts, explore raw transcription mode. |
| API costs exceed budget | Medium — limits usage | Track cost per conversation from day 1. Consider GPT-4o-mini as cheaper LLM fallback. |

## 12. Success Metrics

| Metric | Target | How to Measure |
|--------|--------|---------------|
| End-to-end latency (p50) | < 3 seconds | Server-side timestamps per pipeline stage |
| End-to-end latency (p95) | < 5 seconds | Server-side timestamps per pipeline stage |
| STT accuracy (Georgian) | > 85% word accuracy | Manual review of 50+ transcribed samples |
| TTS naturalness | > 3.5/5 MOS score | Self-rating of 20+ response samples |
| Conversation completion rate | > 70% | Sessions with 3+ successful turns / total sessions |
| Full voice loop working | Yes/No | Can hold a 5-turn Georgian conversation without errors |

## 13. Development Plan

### Timeline: 5 weeks (solo developer, new to LiveKit)

| Week | Phase | Deliverables |
|------|-------|-------------|
| **0** | **Learning + Validation** | Complete LiveKit voice agent tutorial. Run official Python examples. Benchmark WisprFlow with 10 Georgian audio samples. Test ElevenLabs Georgian TTS with 10 text samples. Verify LiveKit Cloud region (move to EU if needed). |
| **1** | **WisprFlow Plugin + Pipeline** | Build custom WisprFlow STT plugin for LiveKit (WebSocket streaming, Opus→PCM transcoding). Get a basic STT→terminal-output loop working. |
| **2** | **Full Voice Pipeline** | Wire up `VoicePipelineAgent`: WisprFlow STT → GPT-4o → ElevenLabs TTS. Conversation logging to PostgreSQL. Tune VAD for Georgian. First end-to-end voice conversation working. |
| **3** | **Frontend** | React frontend with LiveKit Client SDK. Voice button with states (idle/listening/processing/speaking). Chat transcript view. Connect to LiveKit room. |
| **4** | **Polish + Testing** | Latency optimization. Error handling and fallback UX. Edge cases (silence, noise, long utterances). Test with Georgian speakers. Measure all success metrics. |

### Key Milestones

- **End of Week 0:** LiveKit tutorial complete + WisprFlow/ElevenLabs Georgian quality confirmed
- **End of Week 1:** WisprFlow custom plugin working in LiveKit (audio in → Georgian text out)
- **End of Week 2:** Full voice loop working (speak Georgian → hear Georgian response)
- **End of Week 3:** Web UI working with voice interaction
- **End of Week 4:** Polished, tested, measurable MVP

## 14. Open Questions (Resolved + Remaining)

### Resolved
- ~~Push-to-talk vs auto-detect?~~ → Push-to-talk for MVP
- ~~Conversation scope?~~ → General Georgian voice assistant. Vertical chosen post-MVP.
- ~~User authentication?~~ → Not needed for MVP
- ~~Server region?~~ → Europe (Frankfurt/Amsterdam). Verify LiveKit Cloud supports this.
- ~~Budget?~~ → $100–500/mo

### Remaining
- What LiveKit Cloud regions are available? Is EU an option, or is the current instance US-only?
- WisprFlow pricing — what's the actual cost per minute/request?
- Does WisprFlow have a "raw transcription" mode (no auto-editing)? Important for names/dates.
- ElevenLabs voice selection — which voice ID sounds best for Georgian? Need to test options.
- Audio storage — local filesystem for MVP, but what's the plan for production? S3? GCS?
- LiveKit Cloud free tier limits — how many concurrent rooms/participants before hitting paid tier?
