"""The commentary pipeline. See docs/agents.md for the full design:

stats engine -> moment ranker -> producer -> caller / analyst / Q&A -> fact-checker -> voice

PLACEHOLDER: until the Caller agent (#13) exists, a template turns ranked moments into lines.
"""
from pydantic import BaseModel

from app.events.models import MatchEvent
from app.stats.engine import StatsEngine
from app.stats.ranker import Moment, rank

CALL_THRESHOLD = 5  # the template only speaks for moments scored this high


class CommentaryLine(BaseModel):
    speaker: str  # "caller" | "analyst"
    excitement: int  # 0 calm, 1 build-up, 2 big moment (drives the voice style)
    text: str
    event_id: str


def excitement_for(moment: Moment) -> int:
    return 2 if moment.score >= 9 else 1 if moment.score >= 6 else 0


class CommentaryPipeline:
    def __init__(self, stats: StatsEngine) -> None:
        self.stats = stats

    async def on_event(self, event: MatchEvent) -> tuple[Moment, list[CommentaryLine]]:
        momentum_before = self.stats.momentum()["value"]
        self.stats.update(event)
        moment = rank(event, self.stats, momentum_before)
        if moment.score < CALL_THRESHOLD:
            return moment, []
        who = event.player or event.team
        if moment.kind == "goal":
            text = f"GOAL! {who} scores for {event.team}!"
        else:
            text = f"{who}: {moment.reason}."
        line = CommentaryLine(speaker="caller", excitement=excitement_for(moment), text=text,
                              event_id=event.id)
        return moment, [line]
