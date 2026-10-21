"""The commentary pipeline. See docs/agents.md for the full design:

stats engine -> moment ranker -> producer -> caller / analyst / Q&A -> fact-checker -> voice

Today: stats engine -> moment ranker -> Caller + Analyst. The Producer (#16) is a few rules:
- the Caller speaks for every moment scored CALL_THRESHOLD or higher
- the Analyst speaks after big moments only (goals, cards, big chances, end of a half), at most
  once every ANALYSIS_COOLDOWN match-seconds, except goals, which always get an analysis

Ranking is instant and runs inline; the agents are slow (Caller ~1 s, Analyst ~3 s), so the
server runs them in the background and the match never waits for them. The Analyst naturally
lands after the Caller, so the audio queue plays them in the right order.

The match story (#30, story.py): every ranked event goes into a match log. When a tactical pattern
first appears, the Analyst flags it at the next stoppage; when a goal pays it off, she gets the line
she really said. At the end of each half she reads the Storyteller's recap.
"""
from collections.abc import Coroutine

from pydantic import BaseModel

from app.agents.analyst import Analyst
from app.agents.caller import Caller
from app.agents.client import agents_enabled
from app.agents.qa import QuestionAnswerer
from app.agents.story import Entry, MatchLog, Storyteller
from app.agents.viewer import ViewerProfile
from app.events.models import MatchEvent
from app.stats.engine import StatsEngine
from app.stats.ranker import Moment, rank

CALL_THRESHOLD = 3
ANALYSIS_THRESHOLD = 5
ANALYSIS_KINDS = {"goal", "card", "chance", "phase", "set_piece"}
ANALYSIS_COOLDOWN = 45  # match seconds between analyses
PATTERN_COOLDOWN = 60  # a new pattern is flagged at a stoppage at least this long after the last analysis


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
        self.full_time = False  # set when the final whistle goes; questions are then about the whole match
        self._last_analysis_at: int | None = None
        self.match_log = MatchLog(stats)
        self.storyteller = Storyteller(self.match_log, use_model=agents_enabled() and analyst is not None)
        self._new_pattern: Entry | None = None  # appeared, not yet flagged on air
        self._flags: dict[str, str] = {}  # event id -> the pattern the Analyst flags there

    def rank(self, event: MatchEvent) -> Moment:
        """Update the stats with the event and score it. Instant: no model involved."""
        momentum_before = self.stats.momentum()["value"]
        self.stats.update(event)
        moment = rank(event, self.stats, momentum_before)
        self.timeline.append((event, moment))
        for entry in self.match_log.record(event, moment):
            if entry.kind == "pattern":
                self._new_pattern = entry
        return moment

    def story_job(self, event: MatchEvent) -> Coroutine | None:
        """A background story update when one is due (every few match minutes), else None."""
        return self.storyteller.update(event.match_seconds) if self.storyteller.due(event) else None

    @staticmethod
    def should_call(moment: Moment) -> bool:
        return moment.score >= CALL_THRESHOLD

    def should_analyse(self, event: MatchEvent, moment: Moment) -> bool:
        """Big moments only, and not too often; or a stoppage to flag a new pattern. Marks the time
        when it says yes."""
        if self.analyst is None or event.type == "Half Start":  # nothing to analyse at kick-off yet
            return False
        if moment.score < ANALYSIS_THRESHOLD or moment.kind not in ANALYSIS_KINDS:
            return self._flag_pattern(event, moment)
        recent = (self._last_analysis_at is not None
                  and event.match_seconds - self._last_analysis_at < ANALYSIS_COOLDOWN)
        if recent and moment.kind != "goal":
            return False
        self._last_analysis_at = event.match_seconds
        return True

    def _flag_pattern(self, event: MatchEvent, moment: Moment) -> bool:
        """A stoppage, a pattern nobody has mentioned yet, and quiet for a while: flag it now."""
        quiet_enough = (self._last_analysis_at is None
                        or event.match_seconds - self._last_analysis_at >= PATTERN_COOLDOWN)
        if not (self._new_pattern and moment.quiet and moment.kind != "phase" and quiet_enough):
            return False
        self._flags[event.id] = self._new_pattern.text.split(": ", 1)[1]  # "Northbridge FC: 6 of 7 ..."
        self._new_pattern = None
        self._last_analysis_at = event.match_seconds
        return True

    def _context(self, event: MatchEvent) -> dict[str, str]:
        """What the Analyst should remember: the story, and for a goal, what she said that it pays off."""
        context = {"STORY_SO_FAR": self.storyteller.story} if self.storyteller.story else {}
        if event.is_goal and (payoff := self._payoff(event)):
            said, what = payoff
            context["YOU SAID EARLIER"] = f"at {said.minute}': {said.text}"
            context["CALLBACK"] = f"As we said at {said.minute}',"
        return context

    def _payoff(self, event: MatchEvent) -> tuple[Entry, str] | None:
        """For a goal: the line Sonia really said that it pays off, and what it was about."""
        route = self.stats.patterns.goal_route(event) or ""
        if "most-used side" in route:
            side = route.split("down the ")[1].split(",")[0]
            words = [f"down the {side}", f"{side} side", f"{side}-side", f"{side} flank", f"{side} wing",
                     f"on the {side}"]
            if said := self.match_log.earlier_line(words, event.team, event.minute):
                return said, f"{side} side"
        if event.play_pattern == "From Counter":
            words = ["press", "high up", "winning the ball", "won the ball", "ball recoveries", "counter"]
            if said := self.match_log.earlier_line(words, event.team, event.minute):
                return said, "pressing"
        return None

    def _with_callback(self, event: MatchEvent, text: str) -> str:
        """The model often skips "refer back", so code adds the callback itself: the minute is always
        the old remark's, never the goal's."""
        if not event.is_goal or not (payoff := self._payoff(event)):
            return text
        said, what = payoff
        if f"{said.minute}'" in text or "as we said" in text.lower():
            return text
        return f"We flagged that {what} at {said.minute}'. {text}"

    async def call(self, event: MatchEvent, moment: Moment) -> CommentaryLine:
        level = self.viewer.level  # the level when the moment happened
        text, excitement, source = await self.caller.call(event, moment, self.stats, self.viewer)
        return CommentaryLine(id=f"{event.id}-caller", speaker="caller", excitement=excitement, text=text,
                              event_id=event.id, source=source, level=level)

    async def analyse(self, event: MatchEvent, moment: Moment) -> CommentaryLine | None:
        level = self.viewer.level
        text = None
        if event.type == "Half End":  # the recap, if the Storyteller has one; else the usual summary
            text = await self.storyteller.recap("half-time" if event.period == 1 else "full-time", level,
                                                self._recap_facts())
        if not text and self.analyst:
            flag = self._flags.pop(event.id, None)
            angle = (f"PATTERN: a pattern has built up. Tell the viewer about it, with its numbers: {flag}"
                     if flag else None)
            text = await self.analyst.analyse(event, moment, self.viewer, self._context(event), angle)
            text = self._with_callback(event, text) if text else text
        if not text:
            return None
        self.match_log.said(event.minute, text)
        return CommentaryLine(id=f"{event.id}-analyst", speaker="analyst", excitement=0, text=text,
                              event_id=event.id, source="model", level=level)

    def _recap_facts(self) -> dict[str, str]:
        stats, possession = self.stats, self.stats.possession()
        return {team: f"{stats.score[team]} goals, {stats.shots[team]} shots, xG {stats.xg[team]:.2f}, "
                      f"{round(possession[team])}% of the ball" for team in (stats.home, stats.away)}

    async def answer(self, question_id: str, question: str) -> CommentaryLine:
        """Answer a viewer's question about the match so far, in the analyst's voice."""
        minute, second = divmod(self.stats.clock, 60)  # the match clock when they asked
        level = self.viewer.level
        if self.qa:
            text = await self.qa.answer(question, minute, second, self.viewer, self.full_time)
            source = "model" if self.qa.agent else "template"
        else:
            text, source = "Sorry, I can't take questions right now. Keep watching!", "template"
        return CommentaryLine(id=f"{question_id}-answer", speaker="analyst", excitement=0, text=text,
                              event_id="", source=source, level=level, reply_to=question_id)
