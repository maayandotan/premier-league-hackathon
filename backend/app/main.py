"""FastAPI app: health check, crowd audio files, and the live match WebSocket."""
import asyncio
import base64
import logging
from collections.abc import Awaitable, Callable

import httpx
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.agents.analyst import Analyst
from app.agents.caller import Caller
from app.agents.client import agents_enabled
from app.agents.pipeline import CommentaryLine, CommentaryPipeline
from app.agents.qa import MAX_QUESTION_CHARS, QuestionAnswerer
from app.agents.viewer import ViewerProfile
from app.config import REPO_ROOT, settings
from app.events.models import MatchEvent
from app.match.replay import replay
from app.match.sources import UnknownSource, load_source
from app.speech.token import speech_token
from app.speech.tts import Speech, speech_enabled
from app.stats.engine import StatsEngine

log = logging.getLogger(__name__)

POST_MATCH_SECONDS = 10 * 60  # after full time, questions stay open this long

app = FastAPI(title="Match Intelligence")
app.add_middleware(CORSMiddleware, allow_origins=[settings.frontend_origin], allow_methods=["*"])
# Crowd ambience and goal roar (CC BY 4.0, see assets/audio/CREDITS.md)
app.mount("/static/audio", StaticFiles(directory=REPO_ROOT / "assets" / "audio"), name="audio")


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/api/speech-token")
async def get_speech_token() -> dict:
    """A 10-minute token so the browser's microphone can talk to Azure Speech without our key."""
    if not speech_enabled():
        raise HTTPException(503, "speech is not configured")
    try:
        return {"token": await speech_token(), "region": settings.azure_speech_region}
    except httpx.HTTPError as error:
        log.warning("speech token failed: %s", error)
        raise HTTPException(502, "speech service unavailable") from error


@app.websocket("/ws/match")
async def match_feed(ws: WebSocket) -> None:
    """Stream a match. Messages, in order of arrival:

    match (info) -> per event: event (+ ranked moment), stats -> commentary (text) -> audio (MP3)
    -> end. Commentary and audio come from background tasks, so the match never waits for them.
    Query params: source (see app.match.sources), speed (1 = real time), start (minute),
    level (beginner | fan | analyst).

    The browser can send {"type": "set_level", "level": ...} at any time; the server answers
    {"type": "level", "level": ...} and the next line follows the new level.
    It can also send {"type": "question", "text": ...}: the server echoes {"type": "question"} and
    the answer arrives later as a commentary line with reply_to, while the match keeps going.
    Questions stay open after full time ("end") until the viewer leaves or POST_MATCH_SECONDS.
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
    analyst = Analyst(stats, {e.id: e for e in match.events}, use_model=agents_enabled())
    viewer = ViewerProfile()
    viewer.set_level(params.get("level", "fan"))
    pipeline = CommentaryPipeline(stats, caller, analyst, viewer)
    pipeline.qa = QuestionAnswerer(stats, pipeline.timeline, {e.id: e for e in match.events},
                                   use_model=agents_enabled())
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

    async def deliver(make_line: Callable[[], Awaitable[CommentaryLine | None]],
                      event: MatchEvent | None) -> None:
        """Wait for an agent's line, then send its text and, when ready, its audio."""
        try:
            line = await make_line()
            if line is None:  # e.g. the Analyst chose silence
                return
            await send({"type": "commentary", "line": line.model_dump()})
            if speech and (audio := await speech.synthesize(line.speaker, line.text, line.excitement)):
                await send({"type": "audio", "line_id": line.id, "excitement": line.excitement,
                            "mp3": base64.b64encode(audio).decode()})
        except WebSocketDisconnect:
            pass
        except Exception:  # one bad line must never stop the match
            log.exception("commentary failed for %s", event.id if event else "a question")

    questions_asked = 0

    async def listen() -> None:
        """Messages from the browser, for the whole match: level changes and viewer questions."""
        nonlocal questions_asked
        try:
            while True:
                try:
                    message = await ws.receive_json()
                except ValueError:  # one bad message: skip it, keep listening for the rest of the match
                    log.warning("ignored a malformed message from the browser")
                    continue
                if not isinstance(message, dict):
                    continue
                kind = message.get("type")
                if kind == "set_level" and viewer.set_level(str(message.get("level"))):
                    await send({"type": "level", "level": viewer.level})
                elif kind == "question" and (text := str(message.get("text", "")).strip()):
                    # The match keeps going: the answer is a background task like any other line.
                    questions_asked += 1
                    question_id = f"q{questions_asked}"
                    minute, second = divmod(stats.clock, 60)
                    await send({"type": "question", "id": question_id, "text": text[:MAX_QUESTION_CHARS],
                                "clock": f"{minute}:{second:02d}"})
                    task = asyncio.create_task(
                        deliver(lambda q=question_id, t=text: pipeline.answer(q, t), None))
                    tasks.add(task)
                    task.add_done_callback(tasks.discard)
        except (WebSocketDisconnect, RuntimeError):
            pass  # the match ended or the viewer left

    listener = asyncio.create_task(listen())
    try:
        await send({"type": "match", "info": match.info.model_dump(exclude_none=True),
                    "audio": speech is not None, "level": viewer.level})
        await caller.warm_up()
        async for event in replay(match.events, speed=speed, start_minute=start):
            moment = pipeline.rank(event)
            await send({"type": "event", "event": event.model_dump(by_alias=True, exclude_none=True),
                        "moment": moment.model_dump()})
            jobs = []
            if pipeline.should_call(moment):
                jobs.append(lambda e=event, m=moment: pipeline.call(e, m))
            if pipeline.should_analyse(event, moment):
                jobs.append(lambda e=event, m=moment: pipeline.analyse(e, m))
            for job in jobs:
                task = asyncio.create_task(deliver(job, event))
                tasks.add(task)
                task.add_done_callback(tasks.discard)
            await send({"type": "stats", "stats": stats.snapshot()})
        if tasks:  # let the last lines finish
            await asyncio.wait(tasks, timeout=10)
        pipeline.full_time = True
        await send({"type": "end", "stats": stats.snapshot()})
        # Full time isn't the end of the conversation: viewers can still ask about the match.
        # Keep listening until they leave, or for POST_MATCH_SECONDS.
        await asyncio.wait({listener}, timeout=POST_MATCH_SECONDS)
        if tasks:
            await asyncio.wait(tasks, timeout=15)  # an answer still on its way
        await ws.close()
    except WebSocketDisconnect:
        pass
    finally:
        listener.cancel()
        for task in tasks:
            task.cancel()
        if speech:
            await speech.close()


# The built website (frontend/dist), served by this same app in production: one container,
# one link. Mounted last so the API, WebSocket and audio routes above take precedence.
SITE = REPO_ROOT / "frontend" / "dist"
if SITE.is_dir():
    app.mount("/", StaticFiles(directory=SITE, html=True), name="site")
