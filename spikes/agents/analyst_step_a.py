"""Analyst, Step A: an agent WITH TOOLS, and the tool-call loop made visible.

The Caller got everything in its input. The Analyst gets the moment and must ASK for numbers:
- Tools are plain Python functions. The docstring tells the model what each one does; the
  parameter types become the schema. The model never runs them: it asks, our code runs them.
- The framework runs the loop (ask -> run tool -> send result -> ask again -> ... -> answer).
- We print every step of the loop so you can see what the model asked for and what it got.

LOCAL ONLY with real data (DATA_POLICY.md). Run from the repo root:
  backend/.venv/bin/python spikes/agents/analyst_step_a.py [source] [minute]
"""
import asyncio
import json
import sys
import time
from pathlib import Path
from typing import Annotated

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))

from agent_framework import Agent  # noqa: E402

from app.agents.client import chat_client  # noqa: E402
from app.agents.describe import as_text, event_fields  # noqa: E402
from app.match.sources import load_source  # noqa: E402
from app.stats.engine import StatsEngine  # noqa: E402
from app.stats.ranker import rank  # noqa: E402

INSTRUCTIONS = """You are the analyst (colour commentator) in a live football broadcast.
The caller has just described a moment. Your job: explain WHY it mattered, in 1-2 short spoken sentences.
Every number you say must come from a tool call. Never estimate or invent a number.
Call only the tools you need. Speak to a football fan: clear, no jargon."""


def build_tools(stats: StatsEngine, events_by_id: dict):
    """The Analyst's tools: thin wrappers over the stats engine for the current moment."""

    def get_score() -> dict:
        """The current score and minute."""
        return {"score": stats.score, "minute": stats.minute}

    def get_possession(recent: Annotated[bool, "True for the last 10 minutes only"] = False) -> dict:
        """Share of possession per team (%), for the whole match or the last 10 minutes."""
        return stats.possession(recent=recent)

    def get_momentum() -> dict:
        """Who has been on top in the last 10 minutes: value -1 (away) to +1 (home), and the leader."""
        return stats.momentum()

    def get_shot_quality(event_id: Annotated[str, "The id of a Shot event"]) -> dict:
        """Expected goals (xG) of a shot: how likely a shot like it is to score, 0-1, with a label."""
        event = events_by_id.get(event_id)
        return (stats.shot_quality(event) if event else None) or {"error": "not a shot"}

    return [get_score, get_possession, get_momentum, get_shot_quality]


def show_loop(response) -> None:
    """Print each message in the conversation the framework ran for us."""
    for message in response.messages:
        for content in message.contents:
            kind = getattr(content, "type", type(content).__name__)
            if kind == "function_call":
                print(f"  🤖 model asks:  {content.name}({content.arguments or ''})")
            elif kind == "function_result":
                print(f"  🧮 our code:    {json.dumps(content.result)[:120]}")
            elif kind == "text" and content.text:
                print(f"  🗣️  answer:      {content.text}")


async def main() -> None:
    source = sys.argv[1] if len(sys.argv) > 1 else "statsbomb:3869685"
    minute = int(sys.argv[2]) if len(sys.argv) > 2 else 80
    match = load_source(source)
    stats = StatsEngine(match.info.home.name, match.info.away.name)
    events_by_id = {e.id: e for e in match.events}

    # Replay up to the first goal at or after `minute`, so the stats are "live" at that moment.
    for event in match.events:
        momentum_before = stats.momentum()["value"]
        stats.update(event)
        moment = rank(event, stats, momentum_before)
        if event.minute >= minute and moment.kind == "goal":
            break

    analyst = Agent(chat_client(), name="analyst", instructions=INSTRUCTIONS,
                    tools=build_tools(stats, events_by_id),
                    default_options={"temperature": 0.4, "max_tokens": 150})
    prompt = as_text(event_fields(event, moment, stats) | {"event_id": event.id})
    print(f"=== THE MOMENT WE SEND ===\n{prompt}\n\n=== THE LOOP ===")
    start = time.perf_counter()
    response = await analyst.run(prompt)
    show_loop(response)
    print(f"\n({time.perf_counter() - start:.1f}s total)")


if __name__ == "__main__":
    asyncio.run(main())
