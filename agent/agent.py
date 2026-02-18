import os
import logging
import asyncio

from dotenv import load_dotenv
from livekit import rtc
from livekit.agents import (
    Agent,
    AgentServer,
    AgentSession,
    JobContext,
    JobProcess,
    MetricsCollectedEvent,
    cli,
    metrics,
)
from livekit.agents.voice import room_io
from livekit.plugins import openai, silero, elevenlabs, google
from livekit.plugins.turn_detector.multilingual import MultilingualModel

from db import ConversationDB
from wisprflow_stt import WisprFlowWebSocketSTT

logger = logging.getLogger("voice-ai")
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".env.local"))

GOOGLE_CREDENTIALS = os.environ.get(
    "GOOGLE_APPLICATION_CREDENTIALS",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "google-credentials.json"),
)

# VAD tuning — lower threshold to detect user's speech more reliably
VAD_ACTIVATION_THRESHOLD = float(os.environ.get("VAD_ACTIVATION_THRESHOLD", "0.4"))
VAD_MIN_SPEECH_DURATION = float(os.environ.get("VAD_MIN_SPEECH_DURATION", "0.2"))
VAD_MIN_SILENCE_DURATION = float(os.environ.get("VAD_MIN_SILENCE_DURATION", "0.6"))

SYSTEM_PROMPT = """\
შენ ხარ მეგობრული და დამხმარე ხელოვნური ინტელექტის ასისტენტი, რომელიც ქართულად საუბრობს.

წესები:
- ყოველთვის უპასუხე ქართულად. თუ მომხმარებელი სხვა ენაზე ლაპარაკობს, მაინც ქართულად უპასუხე, თუ სხვა რამ არ მოგთხოვეს.
- პასუხები იყოს მოკლე: მაქსიმუმ 2-3 წინადადება. გრძელი პასუხები ხმოვან ინტერფეისში ცუდად მუშაობს.
- იყავი ბუნებრივი და საუბრის ტონით. მოერიდე ბულეტ-პოინტებს, კოდს, URL-ებს ან ნებისმიერ რამეს, რაც ხმით კარგად არ ჟღერს.
- პატიოსნად აღიარე შენი შეზღუდვები.
- დამხმარე იყავი, მაგრამ ლაკონური.\
"""


STT_PROVIDER = os.environ.get("STT_PROVIDER", "elevenlabs")


def get_stt_provider():
    """Create the STT provider based on STT_PROVIDER env var."""
    if STT_PROVIDER == "wisprflow":
        # WisprFlow doesn't have a native LiveKit plugin, use ElevenLabs as fallback
        # The custom WisprFlow integration is handled in VoiceAssistant.stt_node
        logger.info("Using custom WisprFlow STT (via stt_node override)")
        return elevenlabs.STT(
            model_id="scribe_v2_realtime",
            language_code="ka",
        )
    elif STT_PROVIDER == "openai":
        return openai.STT(model="whisper-1")
    else:
        # Default: ElevenLabs Scribe v2
        return elevenlabs.STT(
            model_id="scribe_v2_realtime",
            language_code="ka",
        )


class VoiceAssistant(Agent):
    def __init__(self) -> None:
        super().__init__(instructions=SYSTEM_PROMPT)
        if STT_PROVIDER == "wisprflow":
            self._wisprflow = WisprFlowWebSocketSTT()
        else:
            self._wisprflow = None

    async def on_enter(self):
        self.session.generate_reply(
            instructions="მოიკითხე მომხმარებელი ქართულად და შესთავაზე შენი დახმარება. იყავი მოკლე.",
            allow_interruptions=False,
        )

    async def stt_node(self, audio, model_settings):
        if self._wisprflow:
            async for event in self._wisprflow.process(audio, model_settings):
                yield event
        else:
            async for event in Agent.stt_node(self, audio, model_settings):
                yield event


db = ConversationDB()
server = AgentServer()
usage_collector = metrics.UsageCollector()


def prewarm(proc: JobProcess):
    proc.userdata["vad"] = silero.VAD.load(
        activation_threshold=VAD_ACTIVATION_THRESHOLD,
        min_speech_duration=VAD_MIN_SPEECH_DURATION,
        min_silence_duration=VAD_MIN_SILENCE_DURATION,
    )
    logger.info(
        f"VAD loaded: threshold={VAD_ACTIVATION_THRESHOLD}, "
        f"min_speech={VAD_MIN_SPEECH_DURATION}s, min_silence={VAD_MIN_SILENCE_DURATION}s"
    )


server.setup_fnc = prewarm


@server.rtc_session()
async def entrypoint(ctx: JobContext):
    await db.init()

    session = AgentSession(
        stt=get_stt_provider(),
        llm=google.LLM(model="gemini-3-flash-preview"),
        tts=google.TTS(
            model_name="gemini-2.5-pro-preview-tts",
            language="en-US",  # English - user's preference
            credentials_file=GOOGLE_CREDENTIALS,
        ),
        vad=ctx.proc.userdata["vad"],
        turn_detection=MultilingualModel(),
    )

    # Log metrics
    @session.on("metrics_collected")
    def _on_metrics(ev: MetricsCollectedEvent):
        metrics.log_metrics(ev.metrics)
        usage_collector.collect(ev.metrics)

    # Log conversation turns to Postgres
    session_id = ctx.room.name or "console"

    @session.on("user_input_transcribed")
    def _on_user_input(ev):
        if hasattr(ev, "transcript") and ev.transcript:
            asyncio.create_task(
                db.log_message(session_id, "user", ev.transcript)
            )

    @session.on("conversation_item_added")
    def _on_conversation_item(ev):
        if hasattr(ev, "item") and hasattr(ev.item, "role") and ev.item.role == "assistant":
            text = ""
            if hasattr(ev.item, "text"):
                text = ev.item.text or ""
            elif hasattr(ev.item, "content"):
                for part in ev.item.content:
                    if hasattr(part, "text"):
                        text += part.text or ""
            if text:
                asyncio.create_task(
                    db.log_message(session_id, "assistant", text)
                )

    # Enable noise cancellation if a module is configured (requires livekit noise cancellation plugin)
    noise_cancellation_module = os.environ.get("NOISE_CANCELLATION_MODULE")
    room_input_opts = None
    if noise_cancellation_module:
        room_input_opts = room_io.RoomInputOptions(
            noise_cancellation=rtc.NoiseCancellationOptions(
                module_id=noise_cancellation_module,
                options="",
            ),
        )
        logger.info(f"Noise cancellation enabled: module={noise_cancellation_module}")
    else:
        logger.info("Noise cancellation disabled (set NOISE_CANCELLATION_MODULE to enable)")

    logger.info(f"Starting session '{session_id}' with stt={STT_PROVIDER}, tts=google")

    await session.start(
        agent=VoiceAssistant(),
        room=ctx.room,
        **({"room_input_options": room_input_opts} if room_input_opts else {}),
    )


if __name__ == "__main__":
    cli.run_app(server)
