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
from app.agents.qa import QuestionAnswerer
from app.agents.viewer import ViewerProfile
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
    level: str = "fan"  # the viewer level it was written for
    reply_to: str | None = None  # the viewer's question this line answers (Q&A)


class CommentaryPipeline:
    def __init__(self, stats: StatsEngine, caller: Caller, analyst: Analyst | None = None,
                 viewer: ViewerProfile | None = None) -> None:
        self.stats = stats
        self.caller = caller
        self.analyst = analyst
        self.viewer = viewer or ViewerProfile()
        self.qa: QuestionAnswerer | None = None
        self.timeline: list[tuple[MatchEvent, Moment]] = []  # what Q&A searches to resolve "that"
        self._last_analysis_at: int | None = None

    def rank(self, event: MatchEvent) -> Moment:
        """Update the stats with the event and score it. Instant: no model involved."""
        momentum_before = self.stats.momentum()["value"]
        self.stats.update(event)
        moment = rank(event, self.stats, momentum_before)
        self.timeline.append((event, moment))
        return moment

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
        level = self.viewer.level  # the level when the moment happened
        text, excitement, source = await self.caller.call(event, moment, self.stats, self.viewer)
        return CommentaryLine(id=f"{event.id}-caller", speaker="caller", excitement=excitement, text=text,
                              event_id=event.id, source=source, level=level)

    async def analyse(self, event: MatchEvent, moment: Moment) -> CommentaryLine | None:
        level = self.viewer.level
        text = await self.analyst.analyse(event, moment, self.viewer) if self.analyst else None
        if not text:
            return None
        return CommentaryLine(id=f"{event.id}-analyst", speaker="analyst", excitement=0, text=text,
                              event_id=event.id, source="model", level=level)

    async def answer(self, question_id: str, question: str) -> CommentaryLine:
        """Answer a viewer's question about the match so far, in the analyst's voice."""
        minute, second = divmod(self.stats.clock, 60)  # the match clock when they asked
        level = self.viewer.level
        if self.qa:
            text = await self.qa.answer(question, minute, second, self.viewer)
            source = "model" if self.qa.agent else "template"
        else:
            text, source = "Sorry, I can't take questions right now. Keep watching!", "template"
        return CommentaryLine(id=f"{question_id}-answer", speaker="analyst", excitement=0, text=text,
                              event_id="", source=source, level=level, reply_to=question_id)
