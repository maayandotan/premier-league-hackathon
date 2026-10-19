"""The Caller's own logic, with a fake agent in place of the model (no network in tests)."""
import asyncio
from types import SimpleNamespace

from app.agents import caller as caller_module
from app.agents.caller import Caller, CallerLine, excitement_for, template_line
from app.agents.describe import event_fields
from app.events.models import MatchEvent, PassDetails, ShotDetails
from app.stats.engine import StatsEngine
from app.stats.ranker import Moment

HOME, AWAY = "Northbridge FC", "Westvale United"
GOAL_MOMENT = Moment(score=10, reason="late equalizer", kind="goal", quiet=True)


def goal_event() -> MatchEvent:
    return MatchEvent(id="g1", index=1, period=2, minute=80, second=0, type="Shot", team=HOME,
                      player="M. Ferro", location=(104.0, 38.0),
                      shot=ShotDetails(outcome="Goal", body_part="Left Foot", type="Open Play"))


class FakeAgent:
    """Stands in for the model: answers with fixed text after a delay, and records what it was sent."""

    def __init__(self, text="Ferro... GOAL!", delay=0.0):
        self.text, self.delay, self.inputs = text, delay, []

    async def run(self, prompt):
        self.inputs.append(prompt)
        await asyncio.sleep(self.delay)
        return SimpleNamespace(value=CallerLine(text=self.text))


def caller_with(agent) -> Caller:
    caller = Caller(use_model=False)
    caller.agent = agent
    return caller


def test_excitement_is_decided_by_code():
    assert excitement_for(GOAL_MOMENT) == 2
    assert excitement_for(Moment(score=4, reason="ball into the box", kind="attack", quiet=False)) == 1
    assert excitement_for(Moment(score=5, reason="booked", kind="card", quiet=True)) == 0


def test_model_line_and_fields_sent_to_the_model():
    stats = StatsEngine(HOME, AWAY)
    agent = FakeAgent()
    text, excitement, source = asyncio.run(caller_with(agent).call(goal_event(), GOAL_MOMENT, stats))
    assert (text, excitement, source) == ("Ferro... GOAL!", 2, "model")
    sent = agent.inputs[0]
    assert "player: M. Ferro" in sent and "body_part: left foot" in sent and "EXCITEMENT: 2" in sent
    assert "Open Play" not in sent  # plain words only, data terms left out


def test_slow_model_falls_back_to_template(monkeypatch):
    monkeypatch.setattr(caller_module, "DEADLINE_SECONDS", 0.05)
    stats = StatsEngine(HOME, AWAY)
    stats.score = {HOME: 2, AWAY: 2}
    text, _, source = asyncio.run(caller_with(FakeAgent(delay=1)).call(goal_event(), GOAL_MOMENT, stats))
    assert source == "template" and text == "GOAL! M. Ferro! 2-2!"


def test_recent_lines_are_remembered_and_sent_back():
    stats = StatsEngine(HOME, AWAY)
    agent = FakeAgent(text="Ferro again...")
    caller = caller_with(agent)
    for _ in range(2):
        asyncio.run(caller.call(goal_event(), GOAL_MOMENT, stats))
    assert "your recent lines: none" in agent.inputs[0]
    assert "your recent lines: Ferro again..." in agent.inputs[1]


def test_without_a_model_the_template_speaks():
    stats = StatsEngine(HOME, AWAY)
    moment = Moment(score=9, reason="penalty awarded", kind="set_piece", quiet=True)
    foul = MatchEvent(id="f", index=2, period=1, minute=20, second=0, type="Foul Committed", team=AWAY)
    assert template_line(foul, moment, stats) == "Penalty to Northbridge FC!"
    text, _, source = asyncio.run(Caller(use_model=False).call(foul, moment, stats))
    assert source == "template" and text == "Penalty to Northbridge FC!"


def test_pass_fields_name_passer_and_receiver():
    stats = StatsEngine(HOME, AWAY)
    event = MatchEvent(id="p", index=3, period=1, minute=61, second=0, type="Pass", team=HOME,
                       player="D. Arlo", location=(70.0, 40.0),
                       **{"pass": PassDetails(recipient="M. Ferro", technique="Through Ball",
                                              end_location=(105.0, 40.0))})
    moment = Moment(score=4, reason="ball into the box", kind="attack", quiet=False)
    fields = event_fields(event, moment, stats)
    assert fields["passer"] == "D. Arlo" and fields["receiver"] == "M. Ferro"
    assert fields["pass_type"] == "through ball" and "player" not in fields


def test_foul_fields_say_who_benefits():
    """A Foul Committed event belongs to the fouling team; the fields must not imply they got the penalty."""
    from app.events.models import FoulDetails

    stats = StatsEngine(HOME, AWAY)
    foul = MatchEvent(id="f2", index=9, period=2, minute=78, second=13, type="Foul Committed", team=AWAY,
                      player="K. Osei", location=(4.0, 40.0), foul=FoulDetails(penalty=True))
    moment = Moment(score=9, reason="penalty awarded", kind="set_piece", quiet=True)
    fields = event_fields(foul, moment, stats)
    assert fields["fouling_team"] == AWAY and fields["awarded_to"] == HOME
    assert fields["fouling_player"] == "K. Osei" and "team" not in fields and "player" not in fields
    assert fields["where"] == "in the box"  # seen from the team that gets the penalty


def test_substitution_fields_say_who_comes_on():
    from app.events.models import SubstitutionDetails

    stats = StatsEngine(HOME, AWAY)
    sub = MatchEvent(id="s1", index=4, period=2, minute=86, second=0, type="Substitution", team=AWAY,
                     player="V. Darrow", substitution=SubstitutionDetails(replacement="M. Ojukwu"))
    moment = Moment(score=3, reason="substitution", kind="stoppage", quiet=True)
    fields = event_fields(sub, moment, stats)
    assert fields["player_off"] == "V. Darrow" and fields["player_on"] == "M. Ojukwu"
    assert "player" not in fields
