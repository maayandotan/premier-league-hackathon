"""The viewer's profile (#15): who the commentary is for. Every AI agent reads it.

One per WebSocket connection. The level can change mid-match: the next line follows it. The team
is the viewer's favourite club (or None): the analyst speaks a little from that fan's side, and Q&A
reads "we" and "my team" as that club.
"""
from dataclasses import dataclass, field
from typing import Literal, get_args

Level = Literal["beginner", "fan", "analyst"]
LEVELS: tuple[str, ...] = get_args(Level)


@dataclass
class ViewerProfile:
    level: Level = "fan"
    language: str = "en"
    explained: set[str] = field(default_factory=set)  # concepts already explained (#15 "grows with you")
    team: str | None = None  # the viewer's club, a Meridian League club name

    def set_team(self, team: str | None) -> bool:
        """Follow a club (or None for neutral). Returns whether it changed."""
        from app.league.clubs import CLUB_BY_NAME  # the league needs nothing from here

        team = team if team in CLUB_BY_NAME else None
        if team == self.team:
            return False
        self.team = team
        return True

    def set_level(self, level: str) -> bool:
        """Change the level if it's a valid one. Returns whether it changed."""
        if level not in LEVELS or level == self.level:
            return False
        self.level = level  # type: ignore[assignment]
        return True
