"""Scripted match stories for the demo.

A scenario fixes the big moments: who scores, when and how, and any red card or big miss.
The simulator plays the rest of the match around them. In a scripted match only the script
scores goals or sends players off, so the story is guaranteed; everything else (passing,
shots that are saved, fouls, yellow cards, corners, substitutions) comes from the simulation.
"""
from dataclasses import dataclass, field
from typing import Literal

from app.synthetic.squads import NORTHBRIDGE, WESTVALE

BeatKind = Literal["goal", "penalty_miss", "big_miss", "red_card"]
GoalStyle = Literal["open_play", "counter", "corner", "penalty", "long_range"]


@dataclass(frozen=True)
class Beat:
    minute: int  # match clock; 90 + n means n minutes into stoppage time
    team: str  # the team that scores, misses, or is sent off
    kind: BeatKind
    style: GoalStyle = "open_play"  # for goals
    player: str | None = None  # who scores / misses / is sent off; picked by the simulator if None


@dataclass(frozen=True)
class Style:
    """How a team plays, so the tactical detectors (#48) find real patterns, not noise."""
    channel: Literal["left", "right"] | None = None  # the side it keeps attacking down
    press: bool = False  # goes after the ball high up the pitch


@dataclass(frozen=True)
class Scenario:
    name: str
    description: str
    beats: list[Beat] = field(default_factory=list)
    home: str = NORTHBRIDGE
    away: str = WESTVALE
    home_strength: float = 0.5  # 0-1: how good the home side is on the ball
    away_strength: float = 0.5
    home_style: Style = Style()
    away_style: Style = Style()

    @property
    def scripted(self) -> bool:
        return bool(self.beats)


SCENARIOS: dict[str, Scenario] = {s.name: s for s in [
    Scenario(
        name="comeback",
        description="Westvale press high and go ahead on the counter. Northbridge keep attacking down the "
                    "right, hit the post, then turn it around: a corner header and a winner from the right "
                    "two minutes from time.",
        beats=[
            Beat(18, WESTVALE, "goal", "counter", player="C. Dunmore"),
            Beat(39, NORTHBRIDGE, "big_miss", player="M. Ferro"),
            Beat(63, NORTHBRIDGE, "goal", "corner", player="L. Mburu"),
            Beat(74, WESTVALE, "penalty_miss", player="C. Dunmore"),
            Beat(88, NORTHBRIDGE, "goal", "open_play", player="M. Ferro"),
        ],
        home_strength=0.55,
        home_style=Style(channel="right"),
        away_style=Style(press=True),
    ),
    Scenario(
        name="red_card",
        description="Northbridge go down to ten men before half-time, concede a penalty, and rescue a "
                    "point with a long-range strike.",
        beats=[
            Beat(31, NORTHBRIDGE, "red_card", player="S. Vantreight"),
            Beat(52, WESTVALE, "goal", "penalty", player="T. Calloway"),
            Beat(79, NORTHBRIDGE, "goal", "long_range", player="D. Arlo"),
        ],
        away_strength=0.55,
        away_style=Style(channel="left"),
    ),
    Scenario(
        name="late_equaliser",
        description="Northbridge lead for most of the match; Westvale equalise from a corner "
                    "in stoppage time.",
        beats=[
            Beat(24, NORTHBRIDGE, "goal", "open_play", player="E. Sorvino"),
            Beat(58, WESTVALE, "big_miss", player="L. Pirozzi"),
            Beat(92, WESTVALE, "goal", "corner", player="K. Osei"),
        ],
        home_style=Style(channel="left"),
        away_style=Style(press=True),
    ),
    Scenario(
        name="open",
        description="No script: goals and red cards come from the simulation alone.",
    ),
]}
