"""The Analyst and the quiet-moment rules, with a fake agent in place of the model."""
import asyncio
from types import SimpleNamespace

from app.agents import analyst as analyst_module
from app.agents.analyst import Analyst, angle_for, build_tools
from app.agents.caller import Caller
from app.agents.pipeline import ANALYSIS_COOLDOWN, CommentaryPipeline
from app.agents.viewer import ViewerProfile
from app.events.models import MatchEvent, PassDetails, ShotDetails
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
    stats = StatsEngine(HOME, AWAY)
    assert angle_for(GOAL, stats).startswith("CONTRAST")
    go_ahead = Moment(score=10, reason="go-ahead goal", kind="goal", quiet=True)
    assert angle_for(go_ahead, stats).startswith("CONTEXT")
    assert angle_for(BOOKING, stats).startswith("PRESSURE")
    assert angle_for(CHANCE, stats).startswith("QUALITY")


def last_ten_minutes(ball: str, danger: str) -> StatsEngine:
    """`ball` keeps passing at the back, `danger` takes the shots."""
    stats = StatsEngine(HOME, AWAY)
    for i in range(12):
        stats.update(MatchEvent(id=f"p{i}", index=i, period=2, minute=80, second=i * 4, type="Pass",
                                team=ball, location=(30.0, 40.0),
                                **{"pass": PassDetails(end_location=(35.0, 40.0))}))
    for i in range(3):
        stats.update(MatchEvent(id=f"s{i}", index=20 + i, period=2, minute=82, second=i * 10, type="Shot",
                                team=danger, location=(108.0, 40.0), shot=ShotDetails(outcome="Saved")))
    return stats


def test_angle_tells_the_truth_when_ball_and_danger_split():
    """Northbridge had the ball, Westvale the chances: the angle must not say Westvale dominated."""
    stats = last_ten_minutes(ball=HOME, danger=AWAY)
    angle = angle_for(GOAL, stats)
    assert angle.startswith(f"SPLIT: {HOME} had more of the ball, but {AWAY} had been more dangerous")
    tools = {t.__name__: t for t in build_tools(stats, {})}
    assert tools["get_run_of_play"]() == {"more_of_the_ball": HOME, "their_share_of_the_ball": "100%",
                                          "more_dangerous": AWAY}


def test_angle_contrast_when_one_team_had_everything():
    assert angle_for(GOAL, last_ten_minutes(ball=AWAY, danger=AWAY)).startswith("CONTRAST")


def test_analysis_gets_the_moment_angle_and_event_id():
    agent = FakeAgent()
    text = asyncio.run(analyst_with(agent).analyse(shot(), GOAL, ViewerProfile(level="beginner")))
    assert text == "That came against the run of play."
    sent = agent.inputs[0]
    assert "ANGLE: CONTRAST" in sent and "event_id: s1" in sent and "player: M. Ferro" in sent
    assert "VIEWER_LEVEL: beginner" in sent


def test_late_or_missing_analyst_stays_quiet(monkeypatch):
    monkeypatch.setattr(analyst_module, "DEADLINE_SECONDS", 0.05)
    viewer = ViewerProfile()
    assert asyncio.run(analyst_with(FakeAgent(delay=1)).analyse(shot(), GOAL, viewer)) is None
    no_model = Analyst(StatsEngine(HOME, AWAY), {}, use_model=False)
    assert asyncio.run(no_model.analyse(shot(), GOAL, viewer)) is None


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


class ShorteningAgent(FakeAgent):
    """Answers too long the first time, then follows the request to shorten."""

    async def run(self, prompt):
        self.inputs.append(prompt)
        if prompt.startswith("Rewrite in at most"):
            return SimpleNamespace(text="Short and sharp: a 9 percent chance.")
        return SimpleNamespace(text=" ".join(["word"] * 50) + ".")


def test_too_long_analysis_is_shortened_by_the_model_not_cut():
    agent = ShorteningAgent()
    text = asyncio.run(analyst_with(agent).analyse(shot(), GOAL, ViewerProfile(level="fan")))
    assert text == "Short and sharp: a 9 percent chance."
    assert agent.inputs[1].startswith("Rewrite in at most 30 words for a fan viewer")


def test_fit_to_words_keeps_whole_sentences():
    assert analyst_module.fit_to_words("One two. Three four five. Six.", 4) == "One two."
    one_long_sentence = "A very long first sentence here."
    assert analyst_module.fit_to_words(one_long_sentence, 2) == one_long_sentence


def test_momentum_tool_speaks_in_words_not_scales():
    stats = StatsEngine(HOME, AWAY)
    for i in range(5):
        stats.update(shot(minute=30, second=i, outcome="Saved", event_id=f"x{i}"))
    momentum = {t.__name__: t for t in build_tools(stats, {})}["get_momentum"]()
    assert momentum == {"on_top": HOME, "how_clearly": "dominating"}


def test_level_switch_applies_to_the_next_line():
    stats = StatsEngine(HOME, AWAY)
    agent = FakeAgent()
    pipeline = CommentaryPipeline(stats, Caller(use_model=False), analyst_with(agent, stats))
    first = asyncio.run(pipeline.analyse(shot(event_id="a"), GOAL))
    pipeline.viewer.set_level("analyst")
    second = asyncio.run(pipeline.analyse(shot(event_id="b"), GOAL))
    assert (first.level, second.level) == ("fan", "analyst")
    assert "VIEWER_LEVEL: analyst" in agent.inputs[1]
    assert not pipeline.viewer.set_level("expert")  # unknown levels are ignored
