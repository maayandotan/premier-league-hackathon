"""Personalization, Step B: fixing what Step A showed.

1. CONSISTENCY: describing chance quality requires get_shot_quality, and the words must
   follow its label (a fan line called a 9.5% shot "a strong chance").
2. NO INTERNAL SCALES at any level: "momentum value -0.3" means nothing even to an analyst.
   xG and possession percentages are fine for analysts; momentum and threat become words.
3. HARD LENGTH CAP IN CODE: the model ignored "max 30 words" once there were several rules.
   We keep whole sentences up to the level's limit (never cut mid-sentence).
4. PLAIN WORDS FOR BEGINNERS: "a tough chance, about 1 in 10", not "a low-probability effort".

Tool calls are printed so we can see what the model actually checked.
LOCAL ONLY with real data (DATA_POLICY.md). Run from the repo root:
  backend/.venv/bin/python spikes/agents/levels_step_b.py
"""
import asyncio
import re
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
- If you say anything about how good a chance was, you MUST have called get_shot_quality in this
  turn, and your words must match its label: "low-probability effort" = a hard/unlikely chance,
  "half chance" = a decent chance, "big chance" = a great chance.
- Never say internal scales or tool names: no "momentum value", "threat", "possession changes per
  minute", no negative numbers. Turn them into words ("Westvale had been on top").
- Don't repeat information already in the input (like the score).
- One or two short sentences. LEAD WITH THE INSIGHT (the surprising part), then the context.

Adapt to VIEWER_LEVEL:
- beginner: someone new to football. Everyday words only, no statistics vocabulary (never
  "probability", "xG", "momentum"). If the moment involves a football term (penalty, booking,
  offside, counter-attack...), explain it in a few plain words. At most one number, said as
  "about 1 in 10" or "more than half the ball". Max 30 words.
- fan: knows the game. Clear football language, numbers said naturally ("a 9 percent chance",
  "58 percent of the ball"). No "xG". Max 30 words.
- analyst: wants the detail. "xG", "progressive passes", "territory" are welcome, with up to two
  numbers (xG as 0.09, possession as %). Max 35 words."""

WORD_LIMITS = {"beginner": 30, "fan": 30, "analyst": 35}
LEVELS = list(WORD_LIMITS)
TARGETS = [(78, "penalty awarded"), (80, "late equalizer"), (86, "booked")]


def fit_to_words(text: str, limit: int) -> str:
    """Keep whole sentences up to the word limit. The model doesn't reliably count words."""
    sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    kept: list[str] = []
    for sentence in sentences:
        if kept and len(" ".join(kept + [sentence]).split()) > limit:
            break
        kept.append(sentence)
    return " ".join(kept)


def tools_called(response) -> list[str]:
    return [c.name for m in response.messages for c in m.contents if getattr(c, "type", "") == "function_call"]


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
                raw = response.text.strip()
                limit = WORD_LIMITS[level]
                note = ""
                if len(raw.split()) > limit:  # too long: ask once to shorten, keeping the insight
                    shorter = await analyst.run(
                        f"Rewrite in at most {limit} words for a {level} viewer. Keep the key insight and "
                        f"every number exactly as it is. Text: {raw}")
                    note = f" [shortened from {len(raw.split())}]"
                    raw = shorter.text.strip()
                text = fit_to_words(raw, limit + 5)  # last-resort safety net
                trimmed = note
                print(f"  {level:>8} ({len(text.split()):>2} words{trimmed}) tools: {', '.join(tools_called(response))}")
                print(f"           {text}")


if __name__ == "__main__":
    asyncio.run(main())
