"""The viewer's profile (#15): who the commentary is for. Every AI agent reads it.

One per WebSocket connection. The level can change mid-match: the next line follows it.
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

    def set_level(self, level: str) -> bool:
        """Change the level if it's a valid one. Returns whether it changed."""
        if level not in LEVELS or level == self.level:
            return False
        self.level = level  # type: ignore[assignment]
        return True
