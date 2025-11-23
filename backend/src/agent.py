from dotenv import load_dotenv
load_dotenv(".env")  # load LIVEKIT_URL, GOOGLE_API_KEY, etc. from backend/.env

import logging
import os
import json
from datetime import datetime

from livekit.agents import (
    Agent,
    AgentSession,
    JobContext,
    JobProcess,
    MetricsCollectedEvent,
    RoomInputOptions,
    WorkerOptions,
    cli,
    metrics,
    tokenize,
    function_tool,
    RunContext,
)
from livekit.plugins import murf, silero, google, deepgram, noise_cancellation
from livekit.plugins.turn_detector.multilingual import MultilingualModel

logger = logging.getLogger("agent")


class Assistant(Agent):
    def __init__(self) -> None:
        # You can change the brand name here, e.g. "Third Wave Coffee", "Starbucks", etc.
        brand_name = "Cafe Coffee Day"

        super().__init__(
            instructions=f"""
You are a friendly, efficient barista at {brand_name}.

Your ONLY job is to take coffee orders and confirm them clearly.

You must maintain and think in terms of this order object:

  order = {{
    "drinkType": string,   # e.g. "latte", "cold coffee", "cappuccino"
    "size": string,        # e.g. "small", "medium", "large"
    "milk": string,        # e.g. "whole milk", "skimmed milk", "soy milk", "oat milk"
    "extras": [string],    # e.g. "extra shot", "whipped cream", "caramel syrup"
    "name": string         # customer's name
  }}

Conversation rules:
- Start by greeting the user as a barista at {brand_name}.
- Ask what they’d like to order.
- Ask follow-up questions until you know ALL of these fields:
  drinkType, size, milk, extras, and name.
- If the user doesn’t care about something (e.g. extras), set it to a reasonable default
  like extras = [] or milk = "regular milk".
- Always confirm the final order in natural language.

VERY IMPORTANT:
- ONLY when you are confident that all fields of the order are known,
  call the tool submit_order with the full order details.
- Do NOT call submit_order early.
- After submit_order is called, let the user know their order has been placed.

Tone:
- Be warm, cheerful, and quick.
- Keep responses concise and easy to understand for voice.
- No emojis or fancy formatting.
            """.strip(),
        )

    # This tool will be called by the LLM when the order is complete.
    @function_tool
    async def submit_order(
        self,
        ctx: RunContext,
        drinkType: str,
        size: str,
        milk: str,
        extras: list[str],
        name: str,
    ) -> str:
        """
        Finalize and save the customer's coffee order.

        Use this tool ONLY after you have asked enough questions
        and all of these values are known:
        - drinkType
        - size
        - milk
        - extras
        - name
        """

        order = {
            "drinkType": drinkType,
            "size": size,
            "milk": milk,
            "extras": extras,
            "name": name,
        }

        # Save state in context so other agents/tasks could use it later.
        ctx.userdata["order"] = order

        # Ensure orders directory exists (relative to backend/)
        os.makedirs("orders", exist_ok=True)

        # Create a timestamped filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filepath = os.path.join("orders", f"order_{timestamp}.json")

        # Write the order to a JSON file
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(order, f, indent=2, ensure_ascii=False)

        logger.info(f"Saved order to {filepath}: {order}")

        # This string is what the agent will say/show to the user
        extras_str = ", ".join(extras) if extras else "no extras"
        return (
            f"Got it! I've placed your order: a {size} {drinkType} "
            f"with {milk} and {extras_str}, for {name}. "
            f"Your order has been saved."
        )


def prewarm(proc: JobProcess):
    proc.userdata["vad"] = silero.VAD.load()


async def entrypoint(ctx: JobContext):
    # Logging setup
    ctx.log_context_fields = {
        "room": ctx.room.name,
    }

    # Voice pipeline
    session = AgentSession(
        # STT: ears
        stt=deepgram.STT(model="nova-3"),

        # LLM: brain
        # Tools from the Assistant class (like submit_order) will be available here.
        llm=google.LLM(
            model="gemini-2.5-flash",
        ),

        # TTS: voice
        tts=murf.TTS(
            voice="en-US-matthew",
            style="Conversation",
            tokenizer=tokenize.basic.SentenceTokenizer(min_sentence_len=2),
            text_pacing=True,
        ),

        # Turn detection & VAD
        turn_detection=MultilingualModel(),
        vad=ctx.proc.userdata["vad"],

        # Allow preemptive generation
        preemptive_generation=True,
    )

    usage_collector = metrics.UsageCollector()

    @session.on("metrics_collected")
    def _on_metrics_collected(ev: MetricsCollectedEvent):
        metrics.log_metrics(ev.metrics)
        usage_collector.collect(ev.metrics)

    async def log_usage():
        summary = usage_collector.get_summary()
        logger.info(f"Usage: {summary}")

    ctx.add_shutdown_callback(log_usage)

    # Start the session (agent + room)
    await session.start(
        agent=Assistant(),
        room=ctx.room,
        room_input_options=RoomInputOptions(
            noise_cancellation=noise_cancellation.BVC(),
        ),
    )

    # Connect to room (user)
    await ctx.connect()


if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint, prewarm_fnc=prewarm))
