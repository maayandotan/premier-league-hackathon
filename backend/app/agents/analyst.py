"""The Analyst agent (#14): explains WHY a moment mattered, with numbers from tools.

Built step by step in spikes/agents/analyst_step_*.py. What we learned:
- Without guidance the model is lazy: it calls the least useful tool and makes vague claims.
- Fix (option C): instructions define a good analysis, and CODE picks the angle from the
  Moment Ranker (it already knows a goal was "against the run of play"). The model still
  chooses the tools, the numbers and the words.
- Metric names must be translated into football words ("a 9 percent chance", not "xG 0.09").
- No template fallback: a generic "why" is worse than silence. If it's late, it stays quiet.
"""
import asyncio
import logging
from typing import Annotated

from agent_framework import Agent

from app.agents.client import chat_client
from app.agents.describe import as_text, event_fields
from app.events.models import MatchEvent
from app.stats.engine import StatsEngine
from app.stats.ranker import Moment

log = logging.getLogger(__name__)

DEADLINE_SECONDS = 7.0  # it speaks in quiet moments, so it can take longer than the Caller

INSTRUCTIONS = """You are the analyst (colour commentator) in a live football broadcast.
The caller has just described a moment. You explain WHY it mattered.

A good analysis gives the viewer ONE insight they couldn't see for themselves, from:
- context: who had been on top before this moment (momentum, recent possession)
- quality: how good the chance was, or how rare the pass was
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


def build_tools(stats: StatsEngine, events_by_id: dict[str, MatchEvent]) -> list:
    """The Analyst's tools: thin wrappers over the live stats engine. The model never runs them;
    it asks, the framework runs them here and sends back the result."""

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
        """How far a pass moved the ball towards goal, and the share of this match's passes as good."""
        event = events_by_id.get(event_id)
        return (stats.pass_rarity(event) if event else None) or {"error": "not a pass"}

    return [get_score, get_possession, get_momentum, get_tempo, get_shots_and_xg, get_shot_quality,
            get_pass_rarity]


class Analyst:
    def __init__(self, stats: StatsEngine, events_by_id: dict[str, MatchEvent], use_model: bool) -> None:
        self.agent = Agent(
            chat_client(),
            name="analyst",
            instructions=INSTRUCTIONS,
            tools=build_tools(stats, events_by_id),
            default_options={"temperature": 0.4, "max_tokens": 150},
        ) if use_model else None
        self.stats = stats

    async def analyse(self, event: MatchEvent, moment: Moment) -> str | None:
        """One or two spoken sentences, or None if there's no model or it was too slow."""
        if not self.agent:
            return None
        fields = event_fields(event, moment, self.stats) | {"event_id": event.id, "ANGLE": angle_for(moment)}
        try:
            response = await asyncio.wait_for(self.agent.run(as_text(fields)), DEADLINE_SECONDS)
            return response.text.strip() or None
        except Exception as error:  # late or failed: silence beats a generic line
            log.warning("analyst stayed quiet: %s", type(error).__name__)
            return None
