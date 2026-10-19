"""The commentary pipeline. See docs/agents.md for the full design:

stats engine -> moment ranker -> producer -> caller / analyst / Q&A -> fact-checker -> voice

Today: stats engine -> moment ranker -> Caller. The Producer (#16) is still a simple rule:
call every moment the ranker scores at or above CALL_THRESHOLD.

Ranking is instant and runs inline; the Caller is slow (~1 s), so the server runs it in the
background and the match never waits for it.
"""
from pydantic import BaseModel

from app.agents.caller import Caller
from app.events.models import MatchEvent
from app.stats.engine import StatsEngine
from app.stats.ranker import Moment, rank

CALL_THRESHOLD = 3


class CommentaryLine(BaseModel):
    id: str
    speaker: str  # "caller" | "analyst"
    excitement: int  # 0 calm, 1 build-up, 2 big moment (drives the voice style)
    text: str
    event_id: str
    source: str = "template"  # "model" (an agent wrote it) or "template" (code fallback)


class CommentaryPipeline:
    def __init__(self, stats: StatsEngine, caller: Caller) -> None:
        self.stats = stats
        self.caller = caller

    def rank(self, event: MatchEvent) -> Moment:
        """Update the stats with the event and score it. Instant: no model involved."""
        momentum_before = self.stats.momentum()["value"]
        self.stats.update(event)
        return rank(event, self.stats, momentum_before)

    @staticmethod
    def should_call(moment: Moment) -> bool:
        return moment.score >= CALL_THRESHOLD

    async def call(self, event: MatchEvent, moment: Moment) -> CommentaryLine:
        text, excitement, source = await self.caller.call(event, moment, self.stats)
        return CommentaryLine(id=f"{event.id}-caller", speaker="caller", excitement=excitement, text=text,
                              event_id=event.id, source=source)
