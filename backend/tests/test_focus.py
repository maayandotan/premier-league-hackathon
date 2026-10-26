"""The pitch points at what Roy's answer is about: code matches the answer to the events its tools
returned."""
import asyncio
from types import SimpleNamespace

from app.agents.caller import Caller
from app.agents.pipeline import CommentaryPipeline
from app.agents.qa import QuestionAnswerer, build_qa_tools
from app.agents.viewer import ViewerProfile
from app.match.sources import load_source
from app.stats.engine import StatsEngine


def match_until(minute: int):
    match = load_source("synthetic:comeback")
    stats = StatsEngine(match.info.home.name, match.info.away.name)
    pipeline = CommentaryPipeline(stats, Caller(use_model=False))
    for event in match.events:
        if event.minute >= minute:
            break
        pipeline.rank(event)
    return match, stats, pipeline.timeline


def answering(text: str, tool: str, *args):
    """A stand-in for the model: calls one of its real tools, then answers with `text`."""
    class Agent:
        def __init__(self, tools):
            self.tools = {t.__name__: t for t in tools}

        async def run(self, prompt, **_):
            self.tools[tool](*args)
            return SimpleNamespace(text=text)
    return Agent


def test_the_answer_about_a_goal_points_at_the_goal():
    match, stats, timeline = match_until(20)
    events = {e.id: e for e in match.events}
    goal = next(e for e, _ in timeline if e.is_goal)
    qa = QuestionAnswerer(stats, timeline, events, use_model=False)
    scorer = goal.player.split(". ")[-1]
    qa.agent = answering(f"{scorer} scored it from a counter-attack.", "get_events_before", 20, 0)(
        build_qa_tools(stats, timeline, events))
    _, extras = asyncio.run(qa.answer_with_extras("Who scored?", 20, 0, ViewerProfile()))
    focus = extras["focus"]
    assert focus["event_id"] == goal.id and focus["kind"] == "goal" and focus["team"] == goal.team
    assert focus["location"] == list(goal.location[:2])


def test_no_clear_match_no_focus():
    match, stats, timeline = match_until(20)
    events = {e.id: e for e in match.events}
    qa = QuestionAnswerer(stats, timeline, events, use_model=False)
    qa.agent = answering("It has been an even game so far.", "get_events_before", 20, 0)(
        build_qa_tools(stats, timeline, events))
    assert asyncio.run(qa.answer_with_extras("How's it going?", 20, 0, ViewerProfile()))[1]["focus"] is None


def test_shots_carry_their_chance_of_going_in():
    _, _, timeline = match_until(90)
    shots = [m for e, m in timeline if e.shot is not None and e.period < 5]
    assert shots and all(m.xg is not None and 0 <= m.xg <= 1 for m in shots)
