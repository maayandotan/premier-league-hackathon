"""A live broadcast can't stop: when something fails mid-match, the match goes on.

Each test breaks one thing (Azure Speech, the model, one commentary line, the browser's
messages, the viewer leaving) and checks the system degrades quietly instead of crashing.
"""
import asyncio
from types import SimpleNamespace

import httpx
import pytest
from fastapi.testclient import TestClient

from app.agents import analyst as analyst_module
from app.agents.analyst import Analyst
from app.agents.caller import Caller
from app.agents.describe import event_fields
from app.agents.pipeline import CommentaryPipeline
from app.agents.qa import MAX_QUESTION_CHARS, QuestionAnswerer
from app.agents.viewer import ViewerProfile
from app.events.models import FoulDetails, MatchEvent, ShotDetails
from app.main import app
from app.speech import tts
from app.speech.tts import Speech
from app.stats.engine import StatsEngine
from app.stats.ranker import Moment

HOME, AWAY = "Northbridge FC", "Westvale United"
client = TestClient(app)


def run_match(url: str, send: list[dict] | None = None) -> list[dict]:
    with client.websocket_connect(url) as ws:
        for message in send or []:
            ws.send_json(message)
        messages = []
        while (message := ws.receive_json())["type"] not in ("end", "error"):
            messages.append(message)
        return messages + [message]


# ---------- Azure Speech ----------

def speech_with(handler) -> Speech:
    speech = Speech()
    speech.client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return speech


def test_speech_sends_ssml_and_returns_mp3(monkeypatch):
    monkeypatch.setattr(tts.settings, "azure_speech_key", "test-key")
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, content=b"ID3-mp3")

    audio = asyncio.run(speech_with(handler).synthesize("caller", "GOAL!", 2))
    assert audio == b"ID3-mp3"
    assert seen[0].headers["Ocp-Apim-Subscription-Key"] == "test-key"
    assert b'style="shouting"' in seen[0].content and b"en-US-GuyNeural" in seen[0].content


@pytest.mark.parametrize("failure", [
    lambda request: httpx.Response(401),  # wrong key
    lambda request: httpx.Response(429),  # free tier quota used up
    lambda request: (_ for _ in ()).throw(httpx.ConnectTimeout("slow")),  # network
])
def test_speech_failure_means_text_only_not_a_crash(failure):
    assert asyncio.run(speech_with(failure).synthesize("analyst", "Calm words.", 0)) is None


def test_speech_token_reports_azure_down(monkeypatch):
    from app import main

    async def broken() -> str:
        raise httpx.ConnectError("down")

    monkeypatch.setattr(main, "speech_enabled", lambda: True)
    monkeypatch.setattr(main, "speech_token", broken)
    assert client.get("/api/speech-token").status_code == 502


# ---------- the match feed ----------

def test_one_broken_line_never_stops_the_match(monkeypatch):
    original = CommentaryPipeline.call
    broken = {"count": 0}

    async def sometimes_broken(self, event, moment):
        if not broken["count"]:
            broken["count"] += 1
            raise RuntimeError("model returned nonsense")
        return await original(self, event, moment)

    monkeypatch.setattr(CommentaryPipeline, "call", sometimes_broken)
    messages = run_match("/ws/match?speed=10000")
    assert broken["count"] == 1
    assert messages[-1]["type"] == "end"
    assert any(m["type"] == "commentary" for m in messages)  # the other lines still came


def test_junk_from_the_browser_is_ignored():
    long_question = "why " * 200
    messages = run_match("/ws/match?speed=1000", send=[
        {"type": "nonsense"},
        {"no_type": True},
        {"type": "question", "text": "   "},  # empty: not a question
        {"type": "set_level", "level": 42},
        {"type": "question", "text": long_question},
    ])
    assert messages[-1]["type"] == "end"
    questions = [m for m in messages if m["type"] == "question"]
    assert len(questions) == 1 and len(questions[0]["text"]) == MAX_QUESTION_CHARS


def test_not_json_from_the_browser_does_not_crash_the_server():
    with client.websocket_connect("/ws/match?speed=10000") as ws:
        ws.send_text("this is not json")
        while ws.receive_json()["type"] not in ("end", "error"):
            pass
    assert client.get("/health").json() == {"status": "ok"}


def test_questions_still_work_after_a_malformed_message():
    """One bad message must not stop the server listening for the rest of the match."""
    with client.websocket_connect("/ws/match?speed=200") as ws:
        assert ws.receive_json()["type"] == "match"
        ws.send_text("this is not json")
        ws.send_json([1, 2])  # JSON, but not an object
        ws.send_json({"type": "question", "text": "Who has been better?"})
        seen = []
        while (message := ws.receive_json())["type"] not in ("end", "error"):
            seen.append(message)
    assert any(m["type"] == "question" for m in seen)


def test_viewer_leaving_mid_match_is_fine():
    for _ in range(3):  # leave right away, several times
        with client.websocket_connect("/ws/match?speed=1") as ws:
            assert ws.receive_json()["type"] == "match"
    assert client.get("/health").json() == {"status": "ok"}


def test_a_full_generated_match_streams_to_the_end():
    messages = run_match("/ws/match?source=synthetic:comeback&speed=1000000")
    assert messages[-1]["type"] == "end"
    assert messages[-1]["stats"]["score"] == {HOME: 2, AWAY: 1}
    assert sum(m["type"] == "event" for m in messages) > 1000


# ---------- the agents ----------

MODEL_DOWN = RuntimeError("model down")


class FailingAgent:
    def __init__(self, error=MODEL_DOWN, delay=0.0):
        self.error, self.delay = error, delay

    async def run(self, prompt):
        await asyncio.sleep(self.delay)
        if self.error:
            raise self.error
        return SimpleNamespace(text="too late")


def goal() -> tuple[MatchEvent, Moment]:
    event = MatchEvent(id="g", index=1, period=2, minute=80, second=0, type="Shot", team=HOME,
                       player="M. Ferro", location=(108.0, 40.0), shot=ShotDetails(outcome="Goal"))
    return event, Moment(score=10, reason="go-ahead goal", kind="goal", quiet=True)


def test_analyst_stays_silent_when_the_model_fails():
    analyst = Analyst(StatsEngine(HOME, AWAY), {}, use_model=False)
    analyst.agent = FailingAgent()
    assert asyncio.run(analyst.analyse(*goal(), ViewerProfile())) is None


def test_analyst_stays_silent_when_too_slow(monkeypatch):
    monkeypatch.setattr(analyst_module, "DEADLINE_SECONDS", 0.05)
    analyst = Analyst(StatsEngine(HOME, AWAY), {}, use_model=False)
    analyst.agent = FailingAgent(error=None, delay=1.0)
    assert asyncio.run(analyst.analyse(*goal(), ViewerProfile())) is None


def test_viewer_always_hears_an_answer_even_when_the_model_fails():
    qa = QuestionAnswerer(StatsEngine(HOME, AWAY), [], {}, use_model=False)
    qa.agent = FailingAgent()
    answer = asyncio.run(qa.answer("Why was that a foul?", 80, 0, ViewerProfile()))
    assert answer and "again" in answer


def test_caller_warm_up_failure_does_not_block_kick_off():
    caller = Caller(use_model=False)
    caller.agent = FailingAgent()
    asyncio.run(caller.warm_up())  # no exception


def test_card_fields_name_the_booked_team():
    stats = StatsEngine(HOME, AWAY)
    foul = MatchEvent(id="c", index=2, period=1, minute=30, second=0, type="Foul Committed", team=AWAY,
                      player="K. Osei", location=(50.0, 40.0), foul=FoulDetails(card="Yellow Card"))
    fields = event_fields(foul, Moment(score=5, reason="booked", kind="card", quiet=True), stats)
    assert fields["card"] == "yellow card" and fields["booked_team"] == AWAY
