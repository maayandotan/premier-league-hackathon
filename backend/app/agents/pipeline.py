"""The commentary pipeline. See docs/agents.md for the full design:

stats engine -> moment ranker -> producer -> caller / analyst / Q&A -> fact-checker -> voice

Today: stats engine -> moment ranker -> Caller + Analyst. The Producer (#16) is a few rules:
- the Caller speaks for every moment scored CALL_THRESHOLD or higher
- the Analyst speaks after big moments only (goals, cards, big chances, end of a half), at most
  once every ANALYSIS_COOLDOWN match-seconds, except goals, which always get an analysis

Ranking is instant and runs inline; the agents are slow (Caller ~1 s, Analyst ~3 s), so the
server runs them in the background and the match never waits for them. The Analyst naturally
lands after the Caller, so the audio queue plays them in the right order.
"""
from pydantic import BaseModel

from app.agents.analyst import Analyst
from app.agents.caller import Caller
from app.events.models import MatchEvent
from app.stats.engine import StatsEngine
from app.stats.ranker import Moment, rank

CALL_THRESHOLD = 3
ANALYSIS_THRESHOLD = 5
ANALYSIS_KINDS = {"goal", "card", "chance", "phase", "set_piece"}
ANALYSIS_COOLDOWN = 45  # match seconds between analyses


class CommentaryLine(BaseModel):
    id: str
    speaker: str  # "caller" | "analyst"
    excitement: int  # 0 calm, 1 build-up, 2 big moment (drives the voice style)
    text: str
    event_id: str
    source: str = "template"  # "model" (an agent wrote it) or "template" (code fallback)


class CommentaryPipeline:
    def __init__(self, stats: StatsEngine, caller: Caller, analyst: Analyst | None = None) -> None:
        self.stats = stats
        self.caller = caller
        self.analyst = analyst
        self._last_analysis_at: int | None = None

    def rank(self, event: MatchEvent) -> Moment:
        """Update the stats with the event and score it. Instant: no model involved."""
        momentum_before = self.stats.momentum()["value"]
        self.stats.update(event)
        return rank(event, self.stats, momentum_before)

    @staticmethod
    def should_call(moment: Moment) -> bool:
        return moment.score >= CALL_THRESHOLD

    def should_analyse(self, event: MatchEvent, moment: Moment) -> bool:
        """Big moments only, and not too often. Marks the time when it says yes."""
        if self.analyst is None or moment.score < ANALYSIS_THRESHOLD or moment.kind not in ANALYSIS_KINDS:
            return False
        recent = (self._last_analysis_at is not None
                  and event.match_seconds - self._last_analysis_at < ANALYSIS_COOLDOWN)
        if recent and moment.kind != "goal":
            return False
        self._last_analysis_at = event.match_seconds
        return True

    async def call(self, event: MatchEvent, moment: Moment) -> CommentaryLine:
        text, excitement, source = await self.caller.call(event, moment, self.stats)
        return CommentaryLine(id=f"{event.id}-caller", speaker="caller", excitement=excitement, text=text,
                              event_id=event.id, source=source)

    async def analyse(self, event: MatchEvent, moment: Moment) -> CommentaryLine | None:
        text = await self.analyst.analyse(event, moment) if self.analyst else None
        if not text:
            return None
        return CommentaryLine(id=f"{event.id}-analyst", speaker="analyst", excitement=0, text=text,
                              event_id=event.id, source="model")
