"""The commentary pipeline. See docs/agents.md for the full design:

stats engine -> moment ranker -> producer -> caller / analyst / Q&A -> fact-checker -> voice

Today: stats engine -> moment ranker -> Caller. The Producer (#16) is still a simple rule:
call every moment the ranker scores at or above CALL_THRESHOLD.
"""
from pydantic import BaseModel

from app.agents.caller import Caller
from app.events.models import MatchEvent
from app.stats.engine import StatsEngine
from app.stats.ranker import Moment, rank

CALL_THRESHOLD = 3


class CommentaryLine(BaseModel):
    speaker: str  # "caller" | "analyst"
    excitement: int  # 0 calm, 1 build-up, 2 big moment (drives the voice style)
    text: str
    event_id: str
    source: str = "template"  # "model" (an agent wrote it) or "template" (code fallback)


class CommentaryPipeline:
    def __init__(self, stats: StatsEngine, caller: Caller) -> None:
        self.stats = stats
        self.caller = caller

    async def on_event(self, event: MatchEvent) -> tuple[Moment, list[CommentaryLine]]:
        momentum_before = self.stats.momentum()["value"]
        self.stats.update(event)
        moment = rank(event, self.stats, momentum_before)
        if moment.score < CALL_THRESHOLD:
            return moment, []
        text, excitement, source = await self.caller.call(event, moment, self.stats)
        line = CommentaryLine(speaker="caller", excitement=excitement, text=text, event_id=event.id,
                              source=source)
        return moment, [line]
