"""The Caller agent (#13): live play-by-play, one short spoken line per moment.

Built and tuned step by step in spikes/agents/ (steps A-D). What we learned is all here:
- clear instructions: max 12 words, spoken style, no filler, no invented adjectives
- structured input fields (app.agents.describe) so it can't mix up who did what
- excitement is decided by code; the model only writes text to match it
- temperature 0.5, and its own recent lines for continuity
- a 2-second deadline: if the model is late or the network fails, a template line is used
"""
import asyncio
import logging
from collections import deque

from agent_framework import Agent
from pydantic import BaseModel

from app.agents.client import chat_client
from app.agents.describe import as_text, event_fields
from app.agents.viewer import ViewerProfile
from app.events.models import MatchEvent
from app.stats.engine import StatsEngine
from app.stats.ranker import Moment

log = logging.getLogger(__name__)

DEADLINE_SECONDS = 2.0

INSTRUCTIONS = """You are the play-by-play caller in a live football broadcast.
Call what is happening right now, the way it sounds when spoken live:
short bursts, ellipses for build-up, exclamations for big moments.
Maximum 12 words.
Describe, don't explain: the analyst handles the "why".
Use only facts from the input fields, and keep who did what exactly as given.
No adjectives about the quality of a shot, pass or player unless the input says so.
No filler: never add mood phrases like "tension rising", "pressure mounts" or
"game on the line". If there is little to say, say less.

The input gives an EXCITEMENT level. Match it:
0 = calm and conversational, no exclamation marks
1 = building: urgency, ellipses
2 = big moment: exclamations, the key word in capitals (e.g. GOAL)

You also get your own recent lines. Keep continuity with them (e.g. "Ferro again..."),
and never repeat a phrase you just used.

Adapt to VIEWER_LEVEL:
- beginner: everyday words. For a football term, add two or three plain words the first time
  ("a penalty, a free shot at goal!"). Max 14 words.
- fan: normal commentary.
- analyst: precise football terms are welcome (through ball, cut-back, line-breaking pass).

Write in the LANGUAGE given. For Spanish: Latin American TV commentary, the way it's said live
("¡GOOOL!", "¡Qué ocasión!", "se va de uno..."); team and player names stay exactly as given."""

# Spanish names for the moments the templates mention; anything else just names the player.
SPANISH_REASONS = {
    "hits the post": "¡al palo!", "big chance": "¡ocasión clara!", "half chance": "intenta...",
    "speculative effort": "prueba de lejos...", "sent off": "¡expulsado!", "booked": "tarjeta amarilla",
    "free kick in shooting range": "tiro libre peligroso", "offside": "fuera de lugar",
    "corner": "tiro de esquina", "sets up a shot": "la prepara...", "ball into the box": "centro al área...",
    "carries into the box": "entra al área...",
    "rare line-breaking pass": "¡qué pase!", "beats a defender in the final third": "se va de uno...",
    "kick-off": "¡arranca el partido!", "foul": "falta",
}


class CallerLine(BaseModel):
    text: str


def excitement_for(moment: Moment) -> int:
    """Code decides how excited a line sounds; the voice and the crowd roar follow the same rule."""
    if moment.score >= 9:
        return 2
    if moment.score >= 4 and moment.kind in ("chance", "attack", "set_piece"):
        return 1
    return 0


def template_line(event: MatchEvent, moment: Moment, stats: StatsEngine, language: str = "en") -> str:
    """The fallback: short, always correct, instant."""
    who = event.player or event.team
    if language == "es":
        return spanish_template(event, moment, stats, who)
    if moment.kind == "goal":
        return f"GOAL! {who}! {stats.score[stats.home]}-{stats.score[stats.away]}!"
    if moment.reason == "penalty awarded":
        return f"Penalty to {stats.away if event.team == stats.home else stats.home}!"
    return f"{who}... {moment.reason.split(',')[0]}..."


def spanish_template(event: MatchEvent, moment: Moment, stats: StatsEngine, who: str) -> str:
    if moment.kind == "goal":
        return f"¡GOL! ¡{who}! ¡{stats.score[stats.home]}-{stats.score[stats.away]}!"
    if moment.reason == "penalty awarded":
        return f"¡Penal para {stats.away if event.team == stats.home else stats.home}!"
    reason = moment.reason.split(",")[0]
    return f"{who}... {SPANISH_REASONS[reason]}" if reason in SPANISH_REASONS else f"{who}..."


class Caller:
    def __init__(self, use_model: bool) -> None:
        self.use_model = use_model
        self.recent: deque[str] = deque(maxlen=3)
        self.agent = Agent(
            chat_client(),
            name="caller",
            instructions=INSTRUCTIONS,
            default_options={"temperature": 0.5, "max_tokens": 60, "response_format": CallerLine},
        ) if use_model else None

    async def warm_up(self) -> None:
        """The first call is slow (sign-in, connection). Do it before the match, not on the first goal."""
        if self.agent:
            try:
                await asyncio.wait_for(self.agent.run("minute: 0\nevent: Half Start\nEXCITEMENT: 0"), 15)
            except Exception as error:  # warm-up is best effort
                log.warning("caller warm-up failed: %s", error)

    async def call(self, event: MatchEvent, moment: Moment, stats: StatsEngine,
                   viewer: ViewerProfile | None = None) -> tuple[str, int, str]:
        """Return (text, excitement, source) where source is "model" or "template"."""
        excitement = excitement_for(moment)
        language = (viewer or ViewerProfile()).language
        text, source = None, "template"
        if self.agent:
            fields = event_fields(event, moment, stats) | {
                "EXCITEMENT": excitement,
                "VIEWER_LEVEL": (viewer or ViewerProfile()).level,
                "LANGUAGE": "Spanish" if language == "es" else "English",
                "your recent lines": " | ".join(self.recent) or "none",
            }
            try:
                response = await asyncio.wait_for(self.agent.run(as_text(fields)), DEADLINE_SECONDS)
                text, source = response.value.text, "model"
            except Exception as error:  # too slow, network, bad output: the broadcast never waits
                log.warning("caller fell back to template: %s", type(error).__name__)
        if not text:
            text = template_line(event, moment, stats, language)
        self.recent.append(text)
        return text, excitement, source
