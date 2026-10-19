"""The commentary pipeline. Planned agents (see docs/architecture.md):

ranking -> producer -> caller / analyst -> fact checker -> viewer level, plus a Q&A agent
for viewer questions. They run in Microsoft Foundry (issue #2) and call the stats
engine as tools.

PLACEHOLDER: a rule-based caller so the skeleton produces commentary end to end.
"""
from pydantic import BaseModel

from app.events.models import MatchEvent
from app.stats.engine import StatsEngine


class CommentaryLine(BaseModel):
    speaker: str  # "caller" | "analyst"
    excitement: int  # 0 calm, 1 build-up, 2 big moment (drives the voice style)
    text: str
    event_id: str


class CommentaryPipeline:
    def __init__(self, stats: StatsEngine) -> None:
        self.stats = stats

    async def on_event(self, event: MatchEvent) -> list[CommentaryLine]:
        self.stats.update(event)
        if event.type == "Shot" and event.details.get("outcome") == "Goal":
            return [CommentaryLine(speaker="caller", excitement=2, event_id=event.id,
                                   text=f"GOAL! {event.player} scores for {event.team}!")]
        if event.type == "Shot":
            return [CommentaryLine(speaker="caller", excitement=1, event_id=event.id,
                                   text=f"{event.player} shoots!")]
        return []
