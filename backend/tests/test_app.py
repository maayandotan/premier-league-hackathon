import asyncio

from fastapi.testclient import TestClient

from app.main import app
from app.match.demo import DEMO_MATCH
from app.match.replay import replay

client = TestClient(app)


def collect(url: str) -> list[dict]:
    with client.websocket_connect(url) as ws:
        messages = []
        while True:
            msg = ws.receive_json()
            messages.append(msg)
            if msg["type"] in ("end", "error"):
                return messages


def test_health():
    assert client.get("/health").json() == {"status": "ok"}


def test_match_feed_streams_info_events_commentary_stats_and_end():
    messages = collect("/ws/match?speed=10000")
    assert messages[0]["type"] == "match" and messages[0]["info"]["home"]["name"] == "Northbridge FC"
    events = [m["event"] for m in messages if m["type"] == "event"]
    lines = [m["line"] for m in messages if m["type"] == "commentary"]
    assert len(events) == len(DEMO_MATCH.events)
    assert "pass" in events[0]  # StatsBomb field name on the wire
    assert any(line["excitement"] == 2 and "GOAL" in line["text"] for line in lines)
    assert messages[-1]["type"] == "end"
    assert messages[-1]["stats"]["score"] == {"Northbridge FC": 1, "Westvale United": 0}


def test_start_minute_fast_forwards_stats():
    messages = collect("/ws/match?speed=10000&start=61")
    events = [m for m in messages if m["type"] == "event"]
    assert len(events) == 1  # only the 61' foul is replayed
    assert messages[-1]["stats"]["score"]["Northbridge FC"] == 1  # the 60' goal still counts


def test_unknown_source_reports_an_error():
    assert collect("/ws/match?source=statsbomb:nope")[-1]["type"] == "error"


def test_replay_waits_match_time_divided_by_speed():
    waits: list[float] = []

    async def fake_sleep(seconds: float) -> None:
        waits.append(seconds)

    async def run() -> list[str]:
        return [e.id async for e in replay(DEMO_MATCH.events, speed=2, sleep=fake_sleep)]

    assert asyncio.run(run()) == ["demo-1", "demo-2", "demo-3", "demo-4"]
    assert waits == [1.5, 1.5, 17.0]  # gaps of 3s, 3s, 34s at double speed
