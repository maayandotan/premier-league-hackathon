"""Personalization, Step A: the same moments explained at three viewer levels.

Design: ONE Analyst agent. The instructions describe all three levels once; each request
carries VIEWER_LEVEL. Moving the slider mid-match changes the very next line.
Note the jargon rule now depends on the level: an analyst viewer WANTS "xG of 0.09".

LOCAL ONLY with real data (DATA_POLICY.md). Run from the repo root:
  backend/.venv/bin/python spikes/agents/levels_step_a.py
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))

from agent_framework import Agent  # noqa: E402

from app.agents.analyst import angle_for, build_tools  # noqa: E402
from app.agents.client import chat_client  # noqa: E402
from app.agents.describe import as_text, event_fields  # noqa: E402
from app.match.sources import load_source  # noqa: E402
from app.stats.engine import StatsEngine  # noqa: E402
from app.stats.ranker import rank  # noqa: E402

INSTRUCTIONS = """You are the analyst (colour commentator) in a live football broadcast.
The caller has just described a moment. You explain WHY it mattered.

A good analysis gives the viewer ONE insight they couldn't see for themselves, from:
- context: who had been on top before this moment
- quality: how good the chance was, or how rare the pass was
- consequence: what it changes

Rules for every level:
- Follow the ANGLE you are given; it was chosen from what the data says about this moment.
- Every number comes from a tool call. Never estimate or invent one.
- No claim about momentum, possession, chance quality or rarity without the matching tool.
- Don't repeat information already in the input (like the score).

Adapt to VIEWER_LEVEL:
- beginner: someone new to football. Everyday words only. If the moment involves a football
  term (penalty, offside, booking, counter-attack...), explain it in a few plain words. At most
  one number, said simply ("a small chance, about 1 in 10"). Max 30 words.
- fan: knows the game. Clear football language, numbers said naturally ("a 9 percent chance",
  "58 percent of the ball"). Never say metric or tool names (no "xG", "threat level",
  "momentum value"). Max 30 words.
- analyst: wants the detail. Precise terms are welcome: xG, progressive passes, territory,
  momentum swing. Two numbers are fine. Max 35 words."""

LEVELS = ["beginner", "fan", "analyst"]
TARGETS = [(78, "penalty awarded"), (80, "late equalizer"), (86, "booked")]


async def main() -> None:
    match = load_source(sys.argv[1] if len(sys.argv) > 1 else "statsbomb:3869685")
    stats = StatsEngine(match.info.home.name, match.info.away.name)
    analyst = Agent(chat_client(), name="analyst", instructions=INSTRUCTIONS,
                    tools=build_tools(stats, {e.id: e for e in match.events}),
                    default_options={"temperature": 0.4, "max_tokens": 160})
    targets = list(TARGETS)
    for event in match.events:
        momentum_before = stats.momentum()["value"]
        stats.update(event)
        moment = rank(event, stats, momentum_before)
        if not targets:
            break
        minute, reason = targets[0]
        if event.minute >= minute and moment.reason.startswith(reason):
            targets.pop(0)
            print(f"\n=== {event.minute}' {moment.reason.upper()} ===")
            base = event_fields(event, moment, stats) | {"event_id": event.id, "ANGLE": angle_for(moment)}
            for level in LEVELS:
                response = await analyst.run(as_text(base | {"VIEWER_LEVEL": level}))
                text = response.text.strip()
                print(f"  {level:>8} ({len(text.split()):>2} words): {text}")


if __name__ == "__main__":
    asyncio.run(main())
