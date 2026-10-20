"""The tactics playbook (docs/football_tactics.md) and how the agents get it."""
import asyncio
from types import SimpleNamespace

import pytest

from app.agents.analyst import Analyst, concept_for
from app.agents.qa import RULES, build_qa_tools
from app.agents.tactics import ALIASES, CONCEPTS, LEVELS, PLAYBOOK_RULES, find_concept
from app.agents.viewer import ViewerProfile
from app.events.models import FoulDetails, MatchEvent, PassDetails, ShotDetails
from app.stats.engine import StatsEngine
from app.stats.ranker import Moment

HOME, AWAY = "Northbridge FC", "Westvale United"
GOAL = Moment(score=10, reason="go-ahead goal", kind="goal", quiet=True)
CHANCE = Moment(score=7, reason="big chance, saved", kind="chance", quiet=False)


def test_every_playbook_concept_is_complete():
    assert set(CONCEPTS) == set(ALIASES)  # a new concept needs words to find it by
    for concept in CONCEPTS.values():
        assert len(concept.idea.split()) > 15 and concept.do_not_claim
        assert set(concept.examples) == set(LEVELS), concept.name
        assert "**" not in concept.idea and not concept.examples["fan"].startswith('"')


@pytest.mark.parametrize("question, concept", [
    ("Why did that counter work?", "Counter-attack and transitions"),
    ("What is pressing?", "Pressing and counter-pressing"),
    ("Why do they keep crossing it?", "Crosses and cut-backs"),
    ("Are Westvale parking the bus?", "Defending deep (the low block)"),
    ("How big a deal is the red card?", "Playing with ten men"),
    ("Why are they going long all the time?", "Build-up: playing out from the back versus going direct"),
])
def test_questions_find_their_concept(question, concept):
    assert find_concept(question).name == concept


def test_unrelated_questions_find_nothing():
    assert find_concept("Who is the referee?") is None


def shot(pattern="Regular Play", outcome="Goal", minute=60, shot_type="Open Play"):
    return MatchEvent(id="s", index=1, period=2, minute=minute, second=0, type="Shot", team=HOME,
                      player="M. Ferro", location=(108.0, 40.0), play_pattern=pattern,
                      shot=ShotDetails(outcome=outcome, type=shot_type))


def test_code_picks_the_concept_from_the_moment():
    stats = StatsEngine(HOME, AWAY)
    assert concept_for(shot("From Counter"), GOAL, stats).name == "Counter-attack and transitions"
    assert concept_for(shot("From Corner"), GOAL, stats).name == "Set pieces"
    assert concept_for(shot(shot_type="Penalty"), GOAL, stats).name == "Set pieces"
    assert concept_for(shot(outcome="Saved"), CHANCE, stats).name == "Chance quality and expected goals"
    assert concept_for(shot(minute=88), GOAL, stats).name == "Game state and the late game"
    assert concept_for(shot(minute=30), GOAL, stats) is None  # nothing to teach: no note
    red = MatchEvent(id="r", index=2, period=1, minute=31, second=0, type="Foul Committed", team=HOME,
                     player="S. Vantreight", foul=FoulDetails(card="Red Card"))
    assert concept_for(red, Moment(score=9, reason="sent off", kind="card", quiet=True), stats).name == \
        "Playing with ten men"
    cross = MatchEvent(id="c", index=3, period=1, minute=20, second=0, type="Pass", team=HOME,
                       location=(100.0, 5.0), **{"pass": PassDetails(cross=True, end_location=(110.0, 40.0))})
    attack = Moment(score=4, reason="ball into the box", kind="attack", quiet=False)
    assert concept_for(cross, attack, stats).name == "Crosses and cut-backs"


def test_sonia_gets_the_concept_at_the_viewers_level():
    class Recorder:
        inputs: list[str] = []

        async def run(self, prompt):
            self.inputs.append(prompt)
            return SimpleNamespace(text="They broke at speed.")

    analyst = Analyst(StatsEngine(HOME, AWAY), {}, use_model=False)
    analyst.agent = Recorder()
    asyncio.run(analyst.analyse(shot("From Counter"), GOAL, ViewerProfile(level="beginner")))
    sent = analyst.agent.inputs[0]
    counter = CONCEPTS["Counter-attack and transitions"]
    assert f"TACTICS: {counter.name}" in sent
    assert f"TACTICS_EXAMPLE: {counter.examples['beginner']}" in sent
    assert counter.examples["analyst"] not in sent  # only this viewer's level
    assert "TACTICS_DO_NOT_CLAIM:" in sent


def test_qa_tool_explains_a_tactic_at_a_level():
    tools = {t.__name__: t for t in build_qa_tools(StatsEngine(HOME, AWAY), [], {})}
    brief = tools["get_tactic"](topic="the high press", level="analyst")
    assert brief["concept"] == "Pressing and counter-pressing"
    pressing = CONCEPTS["Pressing and counter-pressing"]
    assert brief["example_line_for_tone_only"] == pressing.examples["analyst"]
    assert "known_topics" in tools["get_tactic"](topic="the referee's haircut")


def test_rules_use_the_playbooks_fuller_offside():
    assert "Level counts as onside" in RULES["offside"]
    assert "throw-in" in RULES["offside"]
    assert RULES["offside"] == PLAYBOOK_RULES["offside"]
    assert "handball" in RULES and "advantage" in RULES


def test_agents_are_told_what_we_cannot_measure():
    """Asked "are they pressing?", a model used possession as proof. Now the brief says plainly."""
    pressing = CONCEPTS["Pressing and counter-pressing"].brief("fan")
    assert pressing["what_we_measure_in_this_match"].startswith("Nothing yet")
    counter = CONCEPTS["Counter-attack and transitions"].brief("fan")
    assert "From Counter" in counter["what_we_measure_in_this_match"]
    assert "#48" not in counter["what_we_measure_in_this_match"]  # planned detectors stay out
