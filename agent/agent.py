import os
import logging
import asyncio
import time
from typing import AsyncIterable, Optional

from dotenv import load_dotenv
from livekit import rtc
from livekit.agents import (
    Agent,
    AgentServer,
    AgentSession,
    JobContext,
    JobProcess,
    MetricsCollectedEvent,
    ModelSettings,
    cli,
    metrics,
    stt,
)
from livekit.plugins import openai, silero, elevenlabs
from livekit.plugins.turn_detector.multilingual import MultilingualModel

from wisprflow_stt import WisprFlowSTTNode
from db import ConversationDB

logger = logging.getLogger("voice-ai")
load_dotenv(".env.local")

# Toggle STT provider: "wisprflow" or "openai"
STT_PROVIDER = os.environ.get("STT_PROVIDER", "openai")

SYSTEM_PROMPT = """\
შენ ხარ მეგობრული და დამხმარე ხელოვნური ინტელექტის ასისტენტი, რომელიც ქართულად საუბრობს.

წესები:
- ყოველთვის უპასუხე ქართულად. თუ მომხმარებელი სხვა ენაზე ლაპარაკობს, მაინც ქართულად უპასუხე, თუ სხვა რამ არ მოგთხოვეს.
- პასუხები იყოს მოკლე: მაქსიმუმ 2-3 წინადადება. გრძელი პასუხები ხმოვან ინტერფეისში ცუდად მუშაობს.
- იყავი ბუნებრივი და საუბრის ტონით. მოერიდე ბულეტ-პოინტებს, კოდს, URL-ებს ან ნებისმიერ რამეს, რაც ხმით კარგად არ ჟღერს.
- პატიოსნად აღიარე შენი შეზღუდვები.
- დამხმარე იყავი, მაგრამ ლაკონური.\
"""


class VoiceAssistant(Agent):
    def __init__(self) -> None:
        super().__init__(instructions=SYSTEM_PROMPT)
        self._wisprflow_node = WisprFlowSTTNode() if STT_PROVIDER == "wisprflow" else None

    async def on_enter(self):
        self.session.generate_reply(
            instructions="მოიკითხე მომხმარებელი ქართულად და შესთავაზე შენი დახმარება. იყავი მოკლე.",
            allow_interruptions=False,
        )

    async def stt_node(
        self,
        audio: AsyncIterable[rtc.AudioFrame],
        model_settings: ModelSettings,
    ) -> Optional[AsyncIterable[stt.SpeechEvent]]:
        if self._wisprflow_node:
            logger.info("Using WisprFlow STT")
            t0 = time.monotonic()

            async def timed_wisprflow():
                async for event in self._wisprflow_node.process(audio, model_settings):
                    elapsed = (time.monotonic() - t0) * 1000
                    logger.info(f"STT (WisprFlow) completed in {elapsed:.0f}ms")
                    yield event

            return timed_wisprflow()

        # Fallback: use default STT (OpenAI Whisper configured in AgentSession)
        logger.info("Using OpenAI Whisper STT")
        return Agent.default.stt_node(self, audio, model_settings)


db = ConversationDB()
server = AgentServer()
usage_collector = metrics.UsageCollector()


def prewarm(proc: JobProcess):
    proc.userdata["vad"] = silero.VAD.load()


server.setup_fnc = prewarm


@server.rtc_session()
async def entrypoint(ctx: JobContext):
    await db.init()

    session = AgentSession(
        # OpenAI Whisper as fallback STT (used when STT_PROVIDER != "wisprflow")
        stt=openai.STT(model="whisper-1", language="ka"),
        llm=openai.LLM(model="gpt-4o"),
        tts=elevenlabs.TTS(model="eleven_multilingual_v2"),
        vad=ctx.proc.userdata["vad"],
        turn_detection=MultilingualModel(),
    )

    # Log metrics
    @session.on("metrics_collected")
    def _on_metrics(ev: MetricsCollectedEvent):
        metrics.log_metrics(ev.metrics)
        usage_collector.collect(ev.metrics)

    # Log conversation turns to SQLite
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

    logger.info(f"Starting session '{session_id}' with STT_PROVIDER={STT_PROVIDER}")

    await session.start(
        agent=VoiceAssistant(),
        room=ctx.room,
    )


if __name__ == "__main__":
    cli.run_app(server)
