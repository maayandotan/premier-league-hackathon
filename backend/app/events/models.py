"""Our internal event model. Every data source is converted into this by an adapter.

PLACEHOLDER: the real schema is being defined in issue #1 (mirroring StatsBomb's
event format). These fields are the minimum the rest of the skeleton needs.
"""
from typing import Any

from pydantic import BaseModel, Field


class MatchEvent(BaseModel):
    id: str
    period: int
    minute: int
    second: int
    type: str  # e.g. "Pass", "Shot", "Foul Committed"
    team: str
    player: str | None = None
    location: tuple[float, float] | None = None  # pitch coordinates, 120 x 80
    details: dict[str, Any] = Field(default_factory=dict)  # type-specific fields (pass, shot...)

    @property
    def match_seconds(self) -> int:
        return self.minute * 60 + self.second
