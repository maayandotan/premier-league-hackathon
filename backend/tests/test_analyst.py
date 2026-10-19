"""The Analyst and the quiet-moment rules, with a fake agent in place of the model."""
import asyncio
from types import SimpleNamespace

from app.agents import analyst as analyst_module
from app.agents.analyst import Analyst, angle_for, build_tools
from app.agents.caller import Caller
from app.agents.pipeline import ANALYSIS_COOLDOWN, CommentaryPipeline
from app.events.models import MatchEvent, ShotDetails
from app.stats.engine import StatsEngine
from app.stats.ranker import Moment

HOME, AWAY = "Northbridge FC", "Westvale United"


def shot(minute=80, second=0, outcome="Goal", event_id="s1"):
    return MatchEvent(id=event_id, index=minute * 60 + second, period=2, minute=minute, second=second,
                      type="Shot", team=HOME, player="M. Ferro", location=(110.0, 40.0),
                      shot=ShotDetails(outcome=outcome))


GOAL = Moment(score=10, reason="late equalizer, against the run of play", kind="goal", quiet=True)
BOOKING = Moment(score=5, reason="booked", kind="card", quiet=True)
CHANCE = Moment(score=7, reason="big chance, saved", kind="chance", quiet=False)
BOX_ENTRY = Moment(score=4, reason="ball into the box", kind="attack", quiet=False)


class FakeAgent:
    def __init__(self, text="That came against the run of play.", delay=0.0):
        self.text, self.delay, self.inputs = text, delay, []

    async def run(self, prompt):
        self.inputs.append(prompt)
        await asyncio.sleep(self.delay)
        return SimpleNamespace(text=self.text)


def analyst_with(agent, stats=None) -> Analyst:
    analyst = Analyst(stats or StatsEngine(HOME, AWAY), {}, use_model=False)
    analyst.agent = agent
    return analyst


def test_angle_comes_from_what_the_ranker_knows():
    assert angle_for(GOAL).startswith("CONTRAST")
    assert angle_for(Moment(score=10, reason="go-ahead goal", kind="goal", quiet=True)).startswith("CONTEXT")
    assert angle_for(BOOKING).startswith("PRESSURE")
    assert angle_for(CHANCE).startswith("QUALITY")


def test_analysis_gets_the_moment_angle_and_event_id():
    agent = FakeAgent()
    text = asyncio.run(analyst_with(agent).analyse(shot(), GOAL))
    assert text == "That came against the run of play."
    sent = agent.inputs[0]
    assert "ANGLE: CONTRAST" in sent and "event_id: s1" in sent and "player: M. Ferro" in sent


def test_late_or_missing_analyst_stays_quiet(monkeypatch):
    monkeypatch.setattr(analyst_module, "DEADLINE_SECONDS", 0.05)
    assert asyncio.run(analyst_with(FakeAgent(delay=1)).analyse(shot(), GOAL)) is None
    assert asyncio.run(Analyst(StatsEngine(HOME, AWAY), {}, use_model=False).analyse(shot(), GOAL)) is None


def test_tools_return_live_numbers():
    stats = StatsEngine(HOME, AWAY)
    goal = shot()
    stats.update(goal)
    tools = {t.__name__: t for t in build_tools(stats, {goal.id: goal})}
    assert tools["get_score"]()["score"] == {HOME: 1, AWAY: 0}
    assert tools["get_shot_quality"](event_id="s1")["xg"] > 0
    assert tools["get_shot_quality"](event_id="nope") == {"error": "not a shot"}
    assert set(tools) >= {"get_momentum", "get_possession", "get_tempo", "get_pass_rarity"}


def test_analyst_speaks_after_big_moments_only_and_not_too_often():
    stats = StatsEngine(HOME, AWAY)
    pipeline = CommentaryPipeline(stats, Caller(use_model=False), analyst_with(FakeAgent(), stats))
    assert not pipeline.should_analyse(shot(minute=10), BOX_ENTRY)  # not a big moment
    assert pipeline.should_analyse(shot(minute=20), BOOKING)
    assert not pipeline.should_analyse(shot(minute=20, second=30), CHANCE)  # within the cooldown
    assert pipeline.should_analyse(shot(minute=20, second=40), GOAL)  # goals always get one
    later = shot(minute=20, second=40 + ANALYSIS_COOLDOWN)
    assert pipeline.should_analyse(later, CHANCE)


def test_pipeline_wraps_the_analysis_as_an_analyst_line():
    stats = StatsEngine(HOME, AWAY)
    pipeline = CommentaryPipeline(stats, Caller(use_model=False), analyst_with(FakeAgent(), stats))
    line = asyncio.run(pipeline.analyse(shot(), GOAL))
    assert (line.speaker, line.excitement, line.source, line.id) == ("analyst", 0, "model", "s1-analyst")
