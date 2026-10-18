"""Statistics engine: plain code, no AI. Computes the numbers the agents explain
(xG, momentum, possession, pass value...) and exposes them as agent tools.

PLACEHOLDER: only counts events for now.
"""
from collections import Counter

from app.events.models import MatchEvent


class StatsEngine:
    def __init__(self) -> None:
        self.events: list[MatchEvent] = []

    def update(self, event: MatchEvent) -> None:
        self.events.append(event)

    def snapshot(self) -> dict:
        return {"events_by_team": dict(Counter(e.team for e in self.events))}
