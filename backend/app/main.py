"""FastAPI app: health check and the live match WebSocket the frontend listens to."""
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from app.agents.pipeline import CommentaryPipeline
from app.config import settings
from app.match.demo import DEMO_EVENTS
from app.match.replay import replay
from app.stats.engine import StatsEngine

app = FastAPI(title="Match Intelligence")
app.add_middleware(CORSMiddleware, allow_origins=[settings.frontend_origin], allow_methods=["*"])


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.websocket("/ws/match")
async def match_feed(ws: WebSocket) -> None:
    """Stream a match: each event, then any commentary lines it produced."""
    await ws.accept()
    pipeline = CommentaryPipeline(StatsEngine())
    speed = float(ws.query_params.get("speed", settings.replay_speed))
    try:
        async for event in replay(DEMO_EVENTS, speed=speed):
            await ws.send_json({"type": "event", "event": event.model_dump()})
            for line in await pipeline.on_event(event):
                await ws.send_json({"type": "commentary", "line": line.model_dump()})
        await ws.send_json({"type": "end", "stats": pipeline.stats.snapshot()})
        await ws.close()
    except WebSocketDisconnect:
        pass
