"""The Q&A agent's tools and flow, with a fake agent in place of the model."""
import asyncio
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.agents.qa import UNAVAILABLE, QuestionAnswerer, build_qa_tools
from app.agents.viewer import ViewerProfile
from app.events.models import FoulDetails, MatchEvent, PassDetails
from app.main import app
from app.stats.engine import StatsEngine
from app.stats.ranker import rank

HOME, AWAY = "Northbridge FC", "Westvale United"


def replay(events):
    stats = StatsEngine(HOME, AWAY)
    timeline = []
    for event in events:
        before = stats.momentum()["value"]
        stats.update(event)
        timeline.append((event, rank(event, stats, before)))
    return stats, timeline


def foul(minute, second, eid, penalty=False):
    return MatchEvent(id=eid, index=minute * 60 + second, period=2, minute=minute, second=second,
                      type="Foul Committed", team=AWAY, player="K. Osei", location=(6.0, 40.0),
                      foul=FoulDetails(penalty=penalty))


def routine_pass(minute, second, eid):
    return MatchEvent(id=eid, index=minute * 60 + second, period=2, minute=minute, second=second, type="Pass",
                      team=HOME, player="D. Arlo", location=(50.0, 40.0),
                      **{"pass": PassDetails(end_location=(52.0, 40.0))})


def tools_for(events):
    stats, timeline = replay(events)
    return {t.__name__: t for t in build_qa_tools(stats, timeline, {e.id: e for e in events})}


def test_events_before_finds_that_moment_and_skips_routine_play():
    events = [foul(60, 0, "early"), foul(78, 13, "pen", penalty=True), routine_pass(78, 15, "p1"),
              foul(80, 0, "later")]
    found = tools_for(events)["get_events_before"](minute=78, second=20)
    assert [e["event_id"] for e in found] == ["early", "pen"]  # nothing after 78:20, no routine pass
    assert found[-1]["awarded_to"] == HOME and found[-1]["moment"] == "penalty awarded"


def test_key_moments_are_the_biggest_of_the_whole_match():
    events = [foul(10, 0, "small"), foul(30, 0, "pen", penalty=True), routine_pass(31, 0, "p1"),
              foul(85, 0, "late")]
    found = tools_for(events)["get_key_moments"](count=2)
    assert found[0]["event_id"] == "pen"  # biggest first, not newest first
    assert "p1" not in [e["event_id"] for e in found]


def test_rules_come_from_our_glossary():
    get_rule = tools_for([routine_pass(1, 0, "p")])["get_rule"]
    assert "second-last defender" in get_rule(topic="Offside")["explanation"]
    assert get_rule(topic="yellow card")["topic"] == "yellow card"
    assert "known_topics" in get_rule(topic="transfer rumours")


def test_match_picture_has_everything_in_one_call():
    picture = tools_for([routine_pass(5, 0, "p")])["get_match_picture"]()
    assert set(picture) == {"on_top_recently", "possession", "possession_last_10_min", "shots", "xg"}


class FakeAgent:
    def __init__(self):
        self.inputs = []

    async def run(self, prompt):
        self.inputs.append(prompt)
        return SimpleNamespace(text="Because the defender tripped him in the box.")


def test_question_carries_the_time_and_level():
    stats, timeline = replay([foul(78, 13, "pen", penalty=True)])
    qa = QuestionAnswerer(stats, timeline, {}, use_model=False)
    qa.agent = FakeAgent()
    text = asyncio.run(qa.answer("Why was that a penalty?", 78, 20, ViewerProfile(level="beginner")))
    assert text == "Because the defender tripped him in the box."
    assert "ASKED_AT: 78:20" in qa.agent.inputs[0] and "VIEWER_LEVEL: beginner" in qa.agent.inputs[0]


def test_without_a_model_the_viewer_still_hears_something():
    stats, timeline = replay([])
    qa = QuestionAnswerer(stats, timeline, {}, use_model=False)
    assert asyncio.run(qa.answer("Who's winning?", 10, 0, ViewerProfile())) == UNAVAILABLE


def test_question_over_the_websocket_is_echoed_and_answered():
    with TestClient(app).websocket_connect("/ws/match?speed=1") as ws:
        assert ws.receive_json()["type"] == "match"
        ws.send_json({"type": "question", "text": "  Why was that a foul?  "})
        seen = []
        while not any(m.get("type") == "commentary" and m["line"].get("reply_to") for m in seen):
            seen.append(ws.receive_json())
    echo = next(m for m in seen if m["type"] == "question")
    answer = next(m["line"] for m in seen if m["type"] == "commentary" and m["line"].get("reply_to"))
    assert echo["text"] == "Why was that a foul?" and echo["id"] == "q1"
    assert answer["reply_to"] == "q1" and answer["speaker"] == "analyst" and answer["text"] == UNAVAILABLE


def test_questions_stay_open_after_full_time():
    with TestClient(app).websocket_connect("/ws/match?speed=10000") as ws:
        while ws.receive_json()["type"] != "end":
            pass
        ws.send_json({"type": "question", "text": "Who was the better team?"})
        seen = []
        while not any(m.get("type") == "commentary" for m in seen):
            seen.append(ws.receive_json())
    assert seen[0]["type"] == "question"
    assert next(m for m in seen if m["type"] == "commentary")["line"]["reply_to"] == "q1"


def test_tools_say_when_in_words_not_clock_times():
    events = [foul(60, 0, "early"), foul(78, 13, "pen", penalty=True)]
    found = tools_for(events)["get_events_before"](minute=78, second=20)
    assert [e["when"] for e in found] == ["in the 60th minute", "a moment ago"]
    assert all("clock" not in e for e in found)
    key = tools_for(events)["get_key_moments"](count=1)
    assert key[0]["when"] == "in the 78th minute"


def test_ordinals():
    from app.agents.qa import ordinal
    assert [ordinal(n) for n in (1, 2, 3, 11, 12, 13, 21, 72, 93)] == \
        ["1st", "2nd", "3rd", "11th", "12th", "13th", "21st", "72nd", "93rd"]


def test_long_answers_are_shortened_once():
    long_answer = "This is a long answer. " * 20
    calls = []

    class Wordy:
        async def run(self, prompt):
            calls.append(prompt)
            return SimpleNamespace(text=long_answer if len(calls) == 1 else "Short and sweet.")

    stats, timeline = replay([routine_pass(5, 0, "p")])
    qa = QuestionAnswerer(stats, timeline, {}, use_model=False)
    qa.agent = Wordy()
    answer = asyncio.run(qa.answer("Why?", 5, 0, ViewerProfile(level="beginner")))
    assert answer == "Short and sweet." and len(calls) == 2
    assert "MAX_WORDS: 40" in calls[0] and "at most 40 words" in calls[1]
