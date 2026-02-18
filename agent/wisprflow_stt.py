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
import struct
import base64
import logging
import asyncio
import json
from typing import AsyncIterable, Optional

import aiohttp
from livekit import rtc
from livekit.agents import stt, ModelSettings

logger = logging.getLogger("wisprflow-stt")

WISPRFLOW_REST_URL = "https://platform-api.wisprflow.ai/api/v1/dash/api"
WISPRFLOW_WS_URL = "wss://platform-api.wisprflow.ai/api/v1/dash/ws"


def resample_48k_to_16k(pcm_data: bytes) -> bytes:
    """Resample 16-bit mono PCM from 48kHz to 16kHz by taking every 3rd sample."""
    # Each sample is 2 bytes (16-bit)
    sample_count = len(pcm_data) // 2
    samples = struct.unpack(f"<{sample_count}h", pcm_data)
    # Simple decimation: take every 3rd sample (48000/16000 = 3)
    resampled = samples[::3]
    return struct.pack(f"<{len(resampled)}h", *resampled)


def pcm_to_wav_base64(pcm_data: bytes, sample_rate: int = 16000) -> str:
    """Convert raw PCM bytes to base64-encoded WAV."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)  # 16-bit
        wf.setframerate(sample_rate)
        wf.writeframes(pcm_data)
    return base64.b64encode(buf.getvalue()).decode("utf-8")


async def transcribe_with_wisprflow(audio_data: bytes, sample_rate: int = 48000) -> Optional[str]:
    """
    Send audio to WisprFlow REST API and return transcription.

    Args:
        audio_data: Raw 16-bit mono PCM bytes
        sample_rate: Input sample rate (will be resampled to 16kHz if needed)

    Returns:
        Transcribed text or None on failure
    """
    api_key = os.environ.get("WISPRFLOW_API_KEY", "")
    if not api_key:
        logger.error("WISPRFLOW_API_KEY not set")
        return None

    # Resample to 16kHz if needed
    if sample_rate == 48000:
        pcm_16k = resample_48k_to_16k(audio_data)
    elif sample_rate == 16000:
        pcm_16k = audio_data
    else:
        logger.error(f"Unsupported sample rate: {sample_rate}")
        return None

    wav_b64 = pcm_to_wav_base64(pcm_16k, 16000)

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
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    text = data.get("text", "").strip()
                    total_time = data.get("total_time", 0)
                    logger.info(f"WisprFlow transcription ({total_time}ms): {text}")
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

    async def process(
        self,
        audio: AsyncIterable[rtc.AudioFrame],
        model_settings: ModelSettings,
    ) -> AsyncIterable[stt.SpeechEvent]:
        """
        Process audio frames and yield SpeechEvents with WisprFlow transcriptions.

        LiveKit's VAD already segments speech — by the time frames arrive here,
        they represent a complete utterance. We accumulate all frames, resample,
        and send to the REST API.
        """
        pcm_buffer = bytearray()
        input_sample_rate = 48000

        async for frame in audio:
            input_sample_rate = frame.sample_rate
            pcm_buffer.extend(frame.data)

        if not pcm_buffer:
            return

        text = await transcribe_with_wisprflow(
            bytes(pcm_buffer), sample_rate=input_sample_rate
        )

        if text:
            yield stt.SpeechEvent(
                type=stt.SpeechEventType.FINAL_TRANSCRIPT,
                alternatives=[
                    stt.SpeechData(
                        text=text,
                        language="ka",
                    )
                ],
            )
        else:
            logger.warning("WisprFlow returned empty transcription")


class WisprFlowWebSocketSTT:
    """
    WebSocket-based streaming STT for lower latency.
    Sends audio chunks incrementally via WisprFlow WebSocket API.

    This is the preferred approach for production use.
    """

    def __init__(self):
        self._api_key = os.environ.get("WISPRFLOW_API_KEY", "")

    async def process(
        self,
        audio: AsyncIterable[rtc.AudioFrame],
        model_settings: ModelSettings,
    ) -> AsyncIterable[stt.SpeechEvent]:
        api_key = self._api_key
        if not api_key:
            logger.error("WISPRFLOW_API_KEY not set")
            return

        ws_url = f"{WISPRFLOW_WS_URL}?api_key=Bearer%20{api_key}"

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
                    input_sample_rate = 48000

                    async for frame in audio:
                        input_sample_rate = frame.sample_rate
                        pcm_data = bytes(frame.data)

                        # Resample to 16kHz
                        if input_sample_rate == 48000:
                            pcm_16k = resample_48k_to_16k(pcm_data)
                        else:
                            pcm_16k = pcm_data

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
