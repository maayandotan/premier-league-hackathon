"""FastAPI app: health check, crowd audio files, and the live match WebSocket."""
import asyncio
import base64
import logging

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.agents.caller import Caller
from app.agents.client import agents_enabled
from app.agents.pipeline import CommentaryPipeline
from app.config import REPO_ROOT, settings
from app.events.models import MatchEvent
from app.match.replay import replay
from app.match.sources import UnknownSource, load_source
from app.speech.tts import Speech, speech_enabled
from app.stats.engine import StatsEngine
from app.stats.ranker import Moment

log = logging.getLogger(__name__)

app = FastAPI(title="Match Intelligence")
app.add_middleware(CORSMiddleware, allow_origins=[settings.frontend_origin], allow_methods=["*"])
# Crowd ambience and goal roar (CC BY 4.0, see assets/audio/CREDITS.md)
app.mount("/static/audio", StaticFiles(directory=REPO_ROOT / "assets" / "audio"), name="audio")


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.websocket("/ws/match")
async def match_feed(ws: WebSocket) -> None:
    """Stream a match. Messages, in order of arrival:

    match (info) -> per event: event (+ ranked moment), stats -> commentary (text) -> audio (MP3)
    -> end. Commentary and audio come from background tasks, so the match never waits for them.
    Query params: source (see app.match.sources), speed (1 = real time), start (minute).
    """
    await ws.accept()
    params = ws.query_params
    try:
        match = load_source(params.get("source", "demo"))
    except UnknownSource as e:
        await ws.send_json({"type": "error", "message": str(e)})
        await ws.close()
        return

    stats = StatsEngine(home=match.info.home.name, away=match.info.away.name)
    caller = Caller(use_model=agents_enabled())
    pipeline = CommentaryPipeline(stats, caller)
    speech = Speech() if speech_enabled() else None
    speed = float(params.get("speed", settings.replay_speed))
    start = int(params.get("start", 0))
    for event in match.events:  # fast-forward: earlier events still count for score and stats
        if event.minute < start:
            stats.update(event)

    send_lock = asyncio.Lock()  # background tasks and the main loop share one socket
    tasks: set[asyncio.Task] = set()

    async def send(message: dict) -> None:
        async with send_lock:
            await ws.send_json(message)

    async def commentate(event: MatchEvent, moment: Moment) -> None:
        try:
            line = await pipeline.call(event, moment)
            await send({"type": "commentary", "line": line.model_dump()})
            if speech and (audio := await speech.synthesize(line.speaker, line.text, line.excitement)):
                await send({"type": "audio", "line_id": line.id, "excitement": line.excitement,
                            "mp3": base64.b64encode(audio).decode()})
        except WebSocketDisconnect:
            pass
        except Exception:  # one bad line must never stop the match
            log.exception("commentary failed for event %s", event.id)

    try:
        await send({"type": "match", "info": match.info.model_dump(exclude_none=True),
                    "audio": speech is not None})
        await caller.warm_up()
        async for event in replay(match.events, speed=speed, start_minute=start):
            moment = pipeline.rank(event)
            await send({"type": "event", "event": event.model_dump(by_alias=True, exclude_none=True),
                        "moment": moment.model_dump()})
            if pipeline.should_call(moment):
                task = asyncio.create_task(commentate(event, moment))
                tasks.add(task)
                task.add_done_callback(tasks.discard)
            await send({"type": "stats", "stats": stats.snapshot()})
        if tasks:  # let the last lines finish
            await asyncio.wait(tasks, timeout=10)
        await send({"type": "end", "stats": stats.snapshot()})
        await ws.close()
    except WebSocketDisconnect:
        pass
    finally:
        for task in tasks:
            task.cancel()
        if speech:
            await speech.close()
