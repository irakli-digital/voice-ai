"""
WisprFlow STT integration for LiveKit Agents.

Provides two approaches:
1. REST API — send complete audio segments after VAD detects end-of-speech
2. WebSocket API — stream audio chunks for real-time partial transcripts

The REST approach is simpler and used as the default.
Both require 16kHz 16-bit mono PCM WAV input (LiveKit sends 48kHz).
"""

import os
import io
import wave
import base64
import logging
import asyncio
import time
from typing import AsyncIterable, Optional

import aiohttp
from livekit import rtc
from livekit.agents import stt, ModelSettings

logger = logging.getLogger("wisprflow-stt")

WISPRFLOW_REST_URL = "https://platform-api.wisprflow.ai/api/v1/dash/api"
WISPRFLOW_WS_URL = "wss://platform-api.wisprflow.ai/api/v1/dash/ws"


def pcm_to_wav_base64(pcm_data: bytes, sample_rate: int = 16000) -> str:
    """Convert raw PCM bytes to base64-encoded WAV."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)  # 16-bit
        wf.setframerate(sample_rate)
        wf.writeframes(pcm_data)
    return base64.b64encode(buf.getvalue()).decode("utf-8")


async def transcribe_with_wisprflow(audio_data: bytes, sample_rate: int = 16000) -> Optional[str]:
    """
    Send audio to WisprFlow REST API and return transcription.

    Args:
        audio_data: Raw 16-bit mono PCM bytes (must already be 16kHz)
        sample_rate: Sample rate of audio_data (should be 16000)

    Returns:
        Transcribed text or None on failure
    """
    api_key = os.environ.get("WISPRFLOW_API_KEY", "")
    if not api_key:
        logger.error("WISPRFLOW_API_KEY not set")
        return None

    duration_s = len(audio_data) / (sample_rate * 2)  # 16-bit = 2 bytes/sample
    logger.info(
        f"WisprFlow API call: {len(audio_data)} bytes, "
        f"{duration_s:.2f}s audio, rate={sample_rate}, "
        f"key={api_key[:8]}..."
    )

    wav_b64 = pcm_to_wav_base64(audio_data, sample_rate)

    payload = {
        "audio": wav_b64,
        "language": ["ka"],  # Georgian
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                WISPRFLOW_REST_URL,
                json=payload,
                headers={
                    "Authorization": api_key,  # Raw API key (not Bearer prefix)
                    "Content-Type": "application/json",
                },
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    logger.debug(f"WisprFlow raw response: {data}")
                    text = data.get("text", "").strip()
                    total_time = data.get("total_time", 0)
                    logger.info(f"WisprFlow transcription ({total_time}ms): {text!r}")
                    return text if text else None
                else:
                    body = await resp.text()
                    logger.error(f"WisprFlow REST error {resp.status}: {body}")
                    return None
    except asyncio.TimeoutError:
        logger.error("WisprFlow REST request timed out")
        return None
    except Exception as e:
        logger.error(f"WisprFlow REST error: {e}")
        return None


class WisprFlowSTTNode:
    """
    Custom STT node that intercepts audio frames from LiveKit,
    buffers them, and sends to WisprFlow REST API after VAD
    signals end-of-speech.

    Usage in Agent subclass:
        async def stt_node(self, audio, model_settings):
            async for event in wisprflow_node.process(audio):
                yield event
    """

    def __init__(self):
        self._api_key = os.environ.get("WISPRFLOW_API_KEY", "")
        self._resampler: Optional[rtc.AudioResampler] = None

    async def process(
        self,
        audio: AsyncIterable[rtc.AudioFrame],
        model_settings: ModelSettings,
    ) -> AsyncIterable[stt.SpeechEvent]:
        """
        Process audio frames in 5-second chunks and yield SpeechEvents.

        The audio stream is continuous (never ends on its own).
        We collect CHUNK_SECONDS of audio, send to WisprFlow REST API,
        yield the result, then repeat.
        """
        CHUNK_SECONDS = 5
        pcm_buffer = bytearray()
        chunk_start = time.monotonic()
        total_frames = 0

        async for frame in audio:
            # Setup resampler on first frame
            if total_frames == 0:
                logger.info(
                    f"First audio frame: sample_rate={frame.sample_rate}, "
                    f"num_channels={frame.num_channels}, "
                    f"data type={type(frame.data).__name__}, "
                    f"data len={len(frame.data)}"
                )
                if frame.sample_rate != 16000:
                    self._resampler = rtc.AudioResampler(
                        input_rate=frame.sample_rate,
                        output_rate=16000,
                        num_channels=frame.num_channels,
                    )
                    logger.info(
                        f"Created AudioResampler: {frame.sample_rate}Hz -> 16000Hz"
                    )
                else:
                    self._resampler = None

            # Resample and buffer
            if self._resampler:
                for rf in self._resampler.push(frame):
                    pcm_buffer.extend(rf.data.tobytes())
            else:
                pcm_buffer.extend(frame.data.tobytes())

            total_frames += 1

            # Every CHUNK_SECONDS, process the buffered audio
            elapsed = time.monotonic() - chunk_start
            if elapsed >= CHUNK_SECONDS and len(pcm_buffer) > 0:
                buf_bytes = len(pcm_buffer)
                logger.info(
                    f"Chunk ready: {buf_bytes} bytes, "
                    f"{elapsed:.1f}s, sending to WisprFlow"
                )

                text = await transcribe_with_wisprflow(
                    bytes(pcm_buffer), sample_rate=16000
                )

                if text:
                    logger.info(f"Transcribed: {text!r}")
                    yield stt.SpeechEvent(
                        type=stt.SpeechEventType.FINAL_TRANSCRIPT,
                        alternatives=[
                            stt.SpeechData(text=text, language="ka")
                        ],
                    )
                else:
                    logger.info(f"No speech in chunk ({buf_bytes} bytes)")

                # Reset for next chunk
                pcm_buffer = bytearray()
                chunk_start = time.monotonic()

        # Process any remaining audio
        if pcm_buffer:
            logger.info(f"Final chunk: {len(pcm_buffer)} bytes")
            text = await transcribe_with_wisprflow(
                bytes(pcm_buffer), sample_rate=16000
            )
            if text:
                yield stt.SpeechEvent(
                    type=stt.SpeechEventType.FINAL_TRANSCRIPT,
                    alternatives=[
                        stt.SpeechData(text=text, language="ka")
                    ],
                )


class WisprFlowWebSocketSTT:
    """
    WebSocket-based streaming STT for lower latency.
    Sends audio chunks incrementally via WisprFlow WebSocket API.

    This is the preferred approach for production use.
    """

    def __init__(self):
        self._api_key = os.environ.get("WISPRFLOW_API_KEY", "")
        self._resampler: Optional[rtc.AudioResampler] = None

    async def process(
        self,
        audio: AsyncIterable[rtc.AudioFrame],
        model_settings: ModelSettings,
    ) -> AsyncIterable[stt.SpeechEvent]:
        api_key = self._api_key
        if not api_key:
            logger.error("WISPRFLOW_API_KEY not set")
            return

        # WisprFlow expects raw API key in query string (not Bearer prefix)
        ws_url = f"{WISPRFLOW_WS_URL}?api_key={api_key}"

        try:
            async with aiohttp.ClientSession() as session:
                async with session.ws_connect(ws_url) as ws:
                    # Send auth context
                    await ws.send_json({
                        "type": "auth",
                        "context": {
                            "languages": ["ka"],
                        },
                    })

                    # Wait for auth confirmation
                    auth_resp = await ws.receive_json()
                    if auth_resp.get("status") != "auth":
                        logger.error(f"WisprFlow WS auth failed: {auth_resp}")
                        return

                    packet_count = 0
                    resampler: Optional[rtc.AudioResampler] = None

                    async for frame in audio:
                        # Create resampler on first frame if needed
                        if packet_count == 0 and frame.sample_rate != 16000:
                            resampler = rtc.AudioResampler(
                                input_rate=frame.sample_rate,
                                output_rate=16000,
                                num_channels=frame.num_channels,
                            )

                        # Resample to 16kHz
                        if resampler:
                            resampled_frames = resampler.push(frame)
                            pcm_chunks = [rf.data.tobytes() for rf in resampled_frames]
                            pcm_16k = b"".join(pcm_chunks)
                        else:
                            pcm_16k = frame.data.tobytes()

                        wav_b64 = pcm_to_wav_base64(pcm_16k, 16000)
                        duration = len(pcm_16k) / (16000 * 2)  # seconds

                        await ws.send_json({
                            "type": "append",
                            "audio": wav_b64,
                            "position": packet_count,
                            "duration": duration,
                        })
                        packet_count += 1

                        # Check for partial transcripts
                        try:
                            msg = await asyncio.wait_for(ws.receive_json(), timeout=0.01)
                            if msg.get("status") == "text" and msg.get("text"):
                                if msg.get("final"):
                                    yield stt.SpeechEvent(
                                        type=stt.SpeechEventType.FINAL_TRANSCRIPT,
                                        alternatives=[
                                            stt.SpeechData(text=msg["text"], language="ka")
                                        ],
                                    )
                                else:
                                    yield stt.SpeechEvent(
                                        type=stt.SpeechEventType.INTERIM_TRANSCRIPT,
                                        alternatives=[
                                            stt.SpeechData(text=msg["text"], language="ka")
                                        ],
                                    )
                        except asyncio.TimeoutError:
                            pass

                    # Signal end of audio
                    await ws.send_json({
                        "type": "commit",
                        "total_packets": packet_count,
                    })

                    # Collect remaining transcriptions
                    while True:
                        try:
                            msg = await asyncio.wait_for(ws.receive_json(), timeout=5.0)
                            if msg.get("status") == "text" and msg.get("text"):
                                yield stt.SpeechEvent(
                                    type=stt.SpeechEventType.FINAL_TRANSCRIPT,
                                    alternatives=[
                                        stt.SpeechData(text=msg["text"], language="ka")
                                    ],
                                )
                                if msg.get("final"):
                                    break
                            elif msg.get("status") == "info":
                                continue
                            elif msg.get("status") == "error":
                                logger.error(f"WisprFlow WS error: {msg}")
                                break
                        except asyncio.TimeoutError:
                            break

        except Exception as e:
            logger.error(f"WisprFlow WebSocket error: {e}")
