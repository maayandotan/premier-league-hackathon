"""FastAPI app: health check and the live match WebSocket the frontend listens to."""
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from app.agents.pipeline import CommentaryPipeline
from app.config import settings
from app.match.replay import replay
from app.match.sources import UnknownSource, load_source
from app.stats.engine import StatsEngine

app = FastAPI(title="Match Intelligence")
app.add_middleware(CORSMiddleware, allow_origins=[settings.frontend_origin], allow_methods=["*"])


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.websocket("/ws/match")
async def match_feed(ws: WebSocket) -> None:
    """Stream a match: its info, then each event with its ranked moment, commentary lines and live stats.

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
    pipeline = CommentaryPipeline(stats)
    speed = float(params.get("speed", settings.replay_speed))
    start = int(params.get("start", 0))
    for event in match.events:  # fast-forward: earlier events still count for score and stats
        if event.minute < start:
            stats.update(event)
    try:
        await ws.send_json({"type": "match", "info": match.info.model_dump(exclude_none=True)})
        async for event in replay(match.events, speed=speed, start_minute=start):
            moment, lines = await pipeline.on_event(event)
            await ws.send_json({
                "type": "event",
                "event": event.model_dump(by_alias=True, exclude_none=True),
                "moment": moment.model_dump(),
            })
            for line in lines:
                await ws.send_json({"type": "commentary", "line": line.model_dump()})
            await ws.send_json({"type": "stats", "stats": stats.snapshot()})
        await ws.send_json({"type": "end", "stats": stats.snapshot()})
        await ws.close()
    except WebSocketDisconnect:
        pass
