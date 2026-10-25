"""The match story (#30): the log, the Storyteller, pattern flags, recaps and payoffs."""
import asyncio
from types import SimpleNamespace

from app.agents.analyst import Analyst
from app.agents.caller import Caller
from app.agents.pipeline import CommentaryPipeline
from app.agents.story import MatchLog, Storyteller
from app.agents.viewer import ViewerProfile
from app.events.models import FoulDetails, MatchEvent, PassDetails, ShotDetails
from app.match.sources import load_source
from app.stats.engine import StatsEngine
from app.stats.ranker import rank

HOME, AWAY = "Northbridge FC", "Westvale United"


def comeback_log(until_minute: int = 200) -> MatchLog:
    match = load_source("synthetic:comeback")
    stats = StatsEngine(HOME, AWAY)
    match_log = MatchLog(stats)
    for event in match.events:
        if event.minute > until_minute:
            break
        before = stats.momentum()["value"]
        stats.update(event)
        match_log.record(event, rank(event, stats, before))
    return match_log


def test_the_log_tells_the_match():
    entries = comeback_log().entries
    goals = [e.text for e in entries if e.kind == "goal"]
    assert len(goals) == 3 and goals[-1].startswith("GOAL Northbridge FC, M. Ferro: Northbridge FC 2-1")
    assert "came down the right, their most-used side" in goals[-1]
    assert any(e.kind == "penalty" for e in entries) and any(e.kind == "half" for e in entries)


def test_each_pattern_is_logged_when_it_appears_not_every_flicker():
    patterns = [e for e in comeback_log().entries if e.kind == "pattern"]
    right = [e for e in patterns if "down the right" in e.text]
    assert len(right) == 1 and right[0].minute < 20  # Northbridge's habit, logged once, early
    assert len(patterns) < 15


def test_earlier_line_finds_what_roy_really_said():
    match_log = comeback_log(until_minute=30)
    match_log.said(16, "Northbridge keep going down the right: 4 of 6 entries there.")
    match_log.said(20, "Westvale have been pressing high.")
    found = match_log.earlier_line(["down the right"], HOME, before_minute=88)
    assert found.minute == 16
    assert match_log.earlier_line(["down the right"], HOME, before_minute=17) is None  # too recent
    assert match_log.earlier_line(["down the right"], AWAY, before_minute=88) is None  # other team


class Scripted:
    def __init__(self, *texts):
        self.texts, self.inputs = list(texts), []

    async def run(self, prompt):
        self.inputs.append(prompt)
        return SimpleNamespace(text=self.texts.pop(0) if self.texts else "")


def test_the_story_is_rejected_if_it_invents_a_number():
    match_log = comeback_log(until_minute=30)
    teller = Storyteller(match_log, use_model=False)
    teller.agent = Scripted("Westvale lead 1-0 after 18 minutes.", "Westvale lead 7-0.")
    asyncio.run(teller.update(30 * 60))
    assert teller.story == "Westvale lead 1-0 after 18 minutes."
    asyncio.run(teller.update(35 * 60))
    assert teller.story == "Westvale lead 1-0 after 18 minutes."  # the invented 7-0 is not kept


def pipeline_with(analyst_agent=None, story_agent=None) -> CommentaryPipeline:
    stats = StatsEngine(HOME, AWAY)
    analyst = Analyst(stats, {}, use_model=False)
    analyst.agent = analyst_agent
    pipeline = CommentaryPipeline(stats, Caller(use_model=False), analyst, ViewerProfile())
    pipeline.storyteller.agent = story_agent
    return pipeline


def entry(i, minute, y=70.0):
    return MatchEvent(id=f"p{i}", index=i, period=1, minute=minute, second=i % 60, type="Pass", team=HOME,
                      location=(70.0, y), possession=i, **{"pass": PassDetails(end_location=(85.0, y))})


def foul(i, minute):
    return MatchEvent(id=f"f{i}", index=i, period=1, minute=minute, second=30, type="Foul Committed",
                      team=AWAY, location=(60.0, 40.0), foul=FoulDetails())


def test_a_new_pattern_is_flagged_at_the_next_stoppage():
    roy = Scripted("Northbridge keep going down the right.")
    pipeline = pipeline_with(analyst_agent=roy)
    for i in range(6):
        pipeline.rank(entry(i, 10 + i))
    stoppage = foul(50, 16)
    assert pipeline.should_analyse(stoppage, pipeline.rank(stoppage))
    line = asyncio.run(pipeline.analyse(stoppage, pipeline.timeline[-1][1]))
    assert line.text == "Northbridge keep going down the right."
    assert "PATTERN" in roy.inputs[0] and "down the right" in roy.inputs[0]
    assert pipeline.match_log.entries[-1].kind == "said"
    second = foul(51, 17)
    assert not pipeline.should_analyse(second, pipeline.rank(second))  # flagged once, and cooling down


def test_a_goal_down_that_side_gets_the_line_she_said():
    roy = Scripted("Northbridge go ahead from their usual side.")
    pipeline = pipeline_with(analyst_agent=roy)
    for i in range(6):
        pipeline.rank(entry(i, 10 + i))
    pipeline.match_log.said(16, "Northbridge keep going down the right.")
    pipeline.rank(entry(40, 80))
    goal = MatchEvent(id="g", index=99, period=2, minute=88, second=0, type="Shot", team=HOME,
                      player="M. Ferro", location=(108.0, 40.0), possession=40,
                      shot=ShotDetails(outcome="Goal"))
    moment = pipeline.rank(goal)
    line = asyncio.run(pipeline.analyse(goal, moment))
    assert line.text == "We flagged that right side at 16'. Northbridge go ahead from their usual side."
    assert "YOU SAID EARLIER: at 16': Roy said" in roy.inputs[0]
    assert "CALLBACK: As we said at 16'," in roy.inputs[0]
    assert "Begin your line with CALLBACK" in roy.inputs[0]


def test_half_time_is_the_storytellers_recap():
    recap = "Westvale lead at the break."
    pipeline = pipeline_with(analyst_agent=Scripted("a summary"), story_agent=Scripted(recap))
    half_end = MatchEvent(id="h", index=1, period=1, minute=47, second=0, type="Half End", team=HOME)
    line = asyncio.run(pipeline.analyse(half_end, pipeline.rank(half_end)))
    assert line.text == recap


def test_no_analysis_at_kick_off():
    """At 0' there's nothing to analyse yet: Roy said "Northbridge have controlled all the possession"."""
    pipeline = pipeline_with(analyst_agent=Scripted("anything"))
    kick_off = MatchEvent(id="k", index=1, period=1, minute=0, second=0, type="Half Start", team=HOME)
    assert not pipeline.should_analyse(kick_off, pipeline.rank(kick_off))
