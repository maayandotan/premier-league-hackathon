"""The Analyst agent (#14): explains WHY a moment mattered, with numbers from tools.

Built step by step in spikes/agents/analyst_step_*.py. What we learned:
- Without guidance the model is lazy: it calls the least useful tool and makes vague claims.
- Fix (option C): instructions define a good analysis, and CODE picks the angle from the
  Moment Ranker (it already knows a goal was "against the run of play"). The model still
  chooses the tools, the numbers and the words.
- Metric names must be translated into football words ("a 9 percent chance", not "xG 0.09").
- No template fallback: a generic "why" is worse than silence. If it's late, it stays quiet.
Personalization (#15, spikes/agents/levels_step_*.py):
- One agent; the instructions describe the three levels and each request says VIEWER_LEVEL.
- Tools speak in words where we don't want numbers spoken ("France, slightly" not "-0.3").
- Too long? Ask the model once to shorten (keeping the insight) instead of cutting the end,
  which removed the punchline.
"""
import asyncio
import logging
import re
from typing import Annotated

from agent_framework import Agent

from app.agents.client import chat_client
from app.agents.describe import as_text, event_fields
from app.agents.viewer import ViewerProfile
from app.events.models import MatchEvent
from app.stats.engine import StatsEngine
from app.stats.ranker import Moment

log = logging.getLogger(__name__)

DEADLINE_SECONDS = 7.0  # it speaks in quiet moments, so it can take longer than the Caller

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
  minute", no negative numbers. Turn them into words ("France had been on top").
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

WORD_LIMITS: dict[str, int] = {"beginner": 30, "fan": 30, "analyst": 35}


def fit_to_words(text: str, limit: int) -> str:
    """Keep whole sentences up to the word limit: a last-resort net, never cuts mid-sentence."""
    sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    kept: list[str] = []
    for sentence in sentences:
        if kept and len(" ".join(kept + [sentence]).split()) > limit:
            break
        kept.append(sentence)
    return " ".join(kept)


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

    # These two speak in words, not internal scales: a model handed "value -0.3" tends to say it,
    # whatever the instructions say. Don't give the model numbers you don't want spoken.
    def get_momentum() -> dict:
        """Who has been on top in the last 10 minutes, and how clearly."""
        m = stats.momentum()
        strength = abs(m["value"])
        how = "dominating" if strength >= 0.6 else "clearly" if strength >= 0.35 else "slightly"
        if not m["leader"]:
            return {"on_top": "neither team", "how_clearly": "evenly matched"}
        return {"on_top": m["leader"], "how_clearly": how}

    def get_tempo() -> dict:
        """How the game feels right now: scrappy (ball changing hands a lot), balanced, or controlled."""
        return {"game_feel": {"chaotic": "scrappy"}.get(stats.tempo()["label"], stats.tempo()["label"])}

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

    async def analyse(self, event: MatchEvent, moment: Moment, viewer: ViewerProfile) -> str | None:
        """One or two sentences at the viewer's level; None without a model or when too slow."""
        if not self.agent:
            return None
        fields = event_fields(event, moment, self.stats) | {
            "event_id": event.id, "ANGLE": angle_for(moment), "VIEWER_LEVEL": viewer.level}
        try:
            return await asyncio.wait_for(self._write(as_text(fields), viewer.level), DEADLINE_SECONDS)
        except Exception as error:  # late or failed: silence beats a generic line
            log.warning("analyst stayed quiet: %s", type(error).__name__)
            return None

    async def _write(self, prompt: str, level: str) -> str | None:
        text = (await self.agent.run(prompt)).text.strip()
        limit = WORD_LIMITS[level]
        if len(text.split()) > limit:  # the model doesn't count words: ask once to shorten
            text = (await self.agent.run(
                f"Rewrite in at most {limit} words for a {level} viewer. Keep the key insight and "
                f"every number exactly as it is. Text: {text}")).text.strip()
        return fit_to_words(text, limit + 5) or None
