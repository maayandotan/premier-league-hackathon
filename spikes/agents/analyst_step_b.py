"""Analyst, Step B: steering the agent (option C).

What's new compared to Step A:
- INSTRUCTIONS define what a good analysis is (context, quality, rarity) and forbid claims
  about momentum/possession/quality without the matching tool.
- An ANGLE HINT chosen by code from the Moment Ranker: the ranker already knows a goal was
  "against the run of play", so we tell the Analyst which angle to take and which tools fit.
  The model still picks the words and the numbers.
- More tools: tempo, pass rarity, shots and xG totals.
- Several moments in one run: goals, a missed chance, a booking, the end of a half.

LOCAL ONLY with real data (DATA_POLICY.md). Run from the repo root:
  backend/.venv/bin/python spikes/agents/analyst_step_b.py
"""
import asyncio
import sys
import time
from pathlib import Path
from typing import Annotated

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))

from agent_framework import Agent  # noqa: E402
from analyst_step_a import show_loop  # noqa: E402

from app.agents.client import chat_client  # noqa: E402
from app.agents.describe import as_text, event_fields  # noqa: E402
from app.events.models import MatchEvent  # noqa: E402
from app.match.sources import load_source  # noqa: E402
from app.stats.engine import StatsEngine  # noqa: E402
from app.stats.ranker import Moment, rank  # noqa: E402

INSTRUCTIONS = """You are the analyst (colour commentator) in a live football broadcast.
The caller has just described a moment. You explain WHY it mattered.

A good analysis gives the viewer ONE insight they couldn't see for themselves, from:
- context: who had been on top before this moment (momentum, recent possession)
- quality: how good the chance was (xG), or how rare the pass was
- consequence: what it changes (score, who needs to react)

Rules:
- Follow the ANGLE you are given; it was chosen from what the data says about this moment.
- Every number comes from a tool call. Never estimate or invent one.
- No claim about momentum, possession, chance quality or rarity unless you called the matching
  tool in this turn. Don't repeat information already in the input (like the score).
- 1-2 short spoken sentences, max 30 words. Speak to a football fan: clear, no jargon.
- Translate metrics into football words. Say "a 9 percent chance", "58 percent of the ball",
  "France have had far more of the dangerous attacks", "the game has become scrappy".
  NEVER say the tool or metric names: no "xG", "expected goals", "threat level", "momentum value",
  "possession changes per minute"."""


def angle_for(moment: Moment) -> str:
    """Code picks the angle from what the ranker already knows; the model fills in the numbers."""
    if moment.kind == "goal":
        if "against the run of play" in moment.reason:
            return ("CONTRAST: the scoring team had NOT been on top. Show who had been dominating "
                    "(get_momentum, get_possession recent) and how good the chance was (get_shot_quality).")
        return ("CONTEXT + QUALITY: was this goal coming (get_momentum) and how good was the chance "
                "(get_shot_quality)?")
    if moment.kind == "chance":
        return "QUALITY: how good was the chance (get_shot_quality), and is this team pushing (get_momentum)?"
    if moment.kind == "attack":
        return "RARITY: how unusual was this pass or run (get_pass_rarity)?"
    if moment.kind == "card":
        return ("PRESSURE: is the booked player's team under the cosh (get_momentum)? Combine it with the "
                "minute and score from the input: what does the card mean for the rest of the match?")
    if moment.kind == "phase":
        return "SUMMARY: who has been the better side so far (get_shots_and_xg, get_possession)?"
    return "CONTEXT: what is the shape of the game right now (get_momentum, get_tempo)?"


def build_tools(stats: StatsEngine, events_by_id: dict[str, MatchEvent]):
    def get_score() -> dict:
        """The current score and minute."""
        return {"score": stats.score, "minute": stats.minute}

    def get_possession(recent: Annotated[bool, "True for the last 10 minutes only"] = False) -> dict:
        """Share of possession per team (%), for the whole match or the last 10 minutes."""
        return stats.possession(recent=recent)

    def get_momentum() -> dict:
        """Who has been on top in the last 10 minutes: value -1 (away) to +1 (home), and the leader."""
        return stats.momentum()

    def get_tempo() -> dict:
        """How chaotic the game is: possession changes per minute over the last 5 minutes."""
        return stats.tempo()

    def get_shots_and_xg() -> dict:
        """Shots and total expected goals (xG) per team so far."""
        return {"shots": stats.shots, "xg": stats.xg}

    def get_shot_quality(event_id: Annotated[str, "The id of a Shot event"]) -> dict:
        """Expected goals (xG) of a shot: how likely a shot like it is to score, 0-1, with a label."""
        event = events_by_id.get(event_id)
        return (stats.shot_quality(event) if event else None) or {"error": "not a shot"}

    def get_pass_rarity(event_id: Annotated[str, "The id of a Pass event"]) -> dict:
        """How far a pass moved the ball towards goal, and the share of this match's passes that did as well."""
        event = events_by_id.get(event_id)
        return (stats.pass_rarity(event) if event else None) or {"error": "not a pass"}

    return [get_score, get_possession, get_momentum, get_tempo, get_shots_and_xg, get_shot_quality,
            get_pass_rarity]


# Moments to analyse: (from minute, kind, optional reason substring). Local real match.
TARGETS = [(52, "phase", "end of the half"), (79, "goal", None), (80, "goal", None),
           (86, "card", None), (93, "chance", None)]


async def main() -> None:
    source = sys.argv[1] if len(sys.argv) > 1 else "statsbomb:3869685"
    match = load_source(source)
    stats = StatsEngine(match.info.home.name, match.info.away.name)
    events_by_id = {e.id: e for e in match.events}
    analyst = Agent(chat_client(), name="analyst", instructions=INSTRUCTIONS,
                    tools=build_tools(stats, events_by_id),
                    default_options={"temperature": 0.4, "max_tokens": 150})
    targets = list(TARGETS)

    for event in match.events:
        momentum_before = stats.momentum()["value"]
        stats.update(event)
        moment = rank(event, stats, momentum_before)
        if not targets:
            break
        minute, kind, reason = targets[0]
        if event.minute >= minute and moment.kind == kind and (reason is None or reason in moment.reason):
            targets.pop(0)
            fields = event_fields(event, moment, stats) | {"event_id": event.id, "ANGLE": angle_for(moment)}
            print(f"\n=== {event.minute}' {moment.reason.upper()} ({event.team}) ===")
            print(f"  angle: {fields['ANGLE'].split(':')[0]}")
            start = time.perf_counter()
            response = await analyst.run(as_text(fields))
            show_loop(response)
            words = len(response.text.split())
            print(f"  ({time.perf_counter() - start:.1f}s, {words} words)")


if __name__ == "__main__":
    asyncio.run(main())
