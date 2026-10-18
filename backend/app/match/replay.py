"""Replays a match's events in (scaled) real time, the way a live feed would deliver them."""
import asyncio
from collections.abc import AsyncIterator, Callable, Iterable

from app.events.models import MatchEvent


async def replay(
    events: Iterable[MatchEvent],
    speed: float = 1.0,
    sleep: Callable[[float], object] = asyncio.sleep,
) -> AsyncIterator[MatchEvent]:
    """Yield events in match order, waiting the match-time gap between them divided by speed."""
    previous: int | None = None
    for event in sorted(events, key=lambda e: (e.period, e.match_seconds)):
        if previous is not None:
            gap = max(0, event.match_seconds - previous) / speed
            if gap:
                await sleep(gap)
        previous = event.match_seconds
        yield event
