from dotenv import load_dotenv
load_dotenv(".env")

import os
import json
import logging
from datetime import datetime

from livekit.agents import (
    Agent,
    AgentSession,
    JobContext,
    JobProcess,
    RoomInputOptions,
    WorkerOptions,
    cli,
    tokenize,
    function_tool,
    RunContext,
    metrics,
    MetricsCollectedEvent,
)

from livekit.plugins import murf, google, deepgram, silero, noise_cancellation
from livekit.plugins.turn_detector.multilingual import MultilingualModel

logger = logging.getLogger("wellness_agent")

LOG_FILE = "wellness_log.json"


# ---------------------------- JSON Persistence -----------------------------

def load_logs_from_disk():
    if not os.path.exists(LOG_FILE):
        return []
    try:
        with open(LOG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def save_logs_to_disk(logs):
    with open(LOG_FILE, "w", encoding="utf-8") as f:
        json.dump(logs, f, indent=2, ensure_ascii=False)


# ---------------------------- Assistant -----------------------------

class WellnessAssistant(Agent):
    def __init__(self):
        instructions = """
You are a supportive and realistic health & wellness companion.
You are NOT a medical professional and MUST NOT give medical advice.

Each session, you:
1. Ask how the user feels (mood, energy, stress).
2. Ask for 1–3 goals or intentions for today.
3. Give small, practical, grounding suggestions.
4. Summarize the mood + goals.
5. Call save_checkin when mood & goals are filled.

Use previous check-in logs if available:
- Mention mood trends gently.
- Keep tone positive and encouraging.
- No diagnosing, no health claims.

Only call save_checkin when ALL required fields are available:
- mood (string)
- goals (list of strings)
- summary (string you create)

Never call save_checkin early.
"""
        super().__init__(instructions=instructions)

    # ----------- TOOL: Save check-in to JSON file -------------

    @function_tool
    async def save_checkin(
        self,
        ctx: RunContext,
        mood: str,
        goals: list[str],
        summary: str,
    ) -> str:
        """
        Save today's wellness check-in to disk.
        """

        entry = {
            "timestamp": datetime.now().isoformat(),
            "mood": mood,
            "goals": goals,
            "summary": summary,
        }

        # Retrieve logs stored in the process
        logs = ctx.proc.userdata.get("wellness_logs", [])
        logs.append(entry)

        # Save on disk
        save_logs_to_disk(logs)

        # Save in memory for next interactions
        ctx.proc.userdata["wellness_logs"] = logs

        return "Your daily check-in has been saved. Thank you for sharing."



# ---------------------------- Entrypoint -----------------------------

def prewarm(proc: JobProcess):
    proc.userdata["vad"] = silero.VAD.load()

    # Load wellness logs ONCE per process boot
    previous_logs = load_logs_from_disk()
    proc.userdata["wellness_logs"] = previous_logs


async def entrypoint(ctx: JobContext):

    ctx.log_context_fields = {"room": ctx.room.name}

    # Voice/LLM Pipeline
    session = AgentSession(
        stt=deepgram.STT(model="nova-3"),
        llm=google.LLM(model="gemini-2.5-flash"),
        tts=murf.TTS(
            voice="en-US-matthew",
            style="Conversation",
            tokenizer=tokenize.basic.SentenceTokenizer(min_sentence_len=2),
            text_pacing=True,
        ),
        turn_detection=MultilingualModel(),
        vad=ctx.proc.userdata["vad"],
        preemptive_generation=True,
    )

    usage = metrics.UsageCollector()

    @session.on("metrics_collected")
    def on_metrics(ev: MetricsCollectedEvent):
        usage.collect(ev.metrics)

    async def log_usage():
        logger.info("Usage summary: %s", usage.get_summary())

    ctx.add_shutdown_callback(log_usage)

    await session.start(
        agent=WellnessAssistant(),
        room=ctx.room,
        room_input_options=RoomInputOptions(
            noise_cancellation=noise_cancellation.BVC()
        ),
    )

    await ctx.connect()


if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint, prewarm_fnc=prewarm))

