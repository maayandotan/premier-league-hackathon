import asyncio

from fastapi.testclient import TestClient

from app.main import app
from app.match.demo import DEMO_EVENTS
from app.match.replay import replay

client = TestClient(app)


def test_health():
    assert client.get("/health").json() == {"status": "ok"}


def test_match_feed_streams_events_commentary_and_end():
    with client.websocket_connect("/ws/match?speed=10000") as ws:
        messages = []
        while True:
            msg = ws.receive_json()
            messages.append(msg)
            if msg["type"] == "end":
                break

    events = [m for m in messages if m["type"] == "event"]
    lines = [m["line"] for m in messages if m["type"] == "commentary"]
    assert len(events) == len(DEMO_EVENTS)
    assert any(line["excitement"] == 2 and "GOAL" in line["text"] for line in lines)


def test_replay_waits_match_time_divided_by_speed():
    waits: list[float] = []

    async def fake_sleep(seconds: float) -> None:
        waits.append(seconds)

    async def run() -> list[str]:
        return [e.id async for e in replay(DEMO_EVENTS, speed=2, sleep=fake_sleep)]

    assert asyncio.run(run()) == ["d1", "d2", "d3", "d4"]
    assert waits == [1.5, 1.5, 17.0]  # gaps of 3s, 3s, 34s at double speed
