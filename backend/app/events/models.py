"""Our internal match model. Every data source is converted into this by an adapter.

Field names and event types follow StatsBomb's open event format, so a provider
feed maps over with little work. Pitch coordinates are 120 x 80: x runs from the
team's own goal line (0) to the opponent's (120), y from left (0) to right (80).
See docs/event-schema.md.
"""
from typing import Any, Literal

from pydantic import BaseModel, Field

Point = tuple[float, float]

# The event types we keep. Adapters drop everything else (e.g. "Ball Receipt*", "Starting XI").
EventType = Literal[
    "Pass", "Carry", "Shot", "Dribble", "Duel", "Interception", "Ball Recovery", "Clearance",
    "Block", "Pressure", "Foul Committed", "Foul Won", "Offside", "Card", "Substitution",
    "Goal Keeper", "Miscontrol", "Dispossessed", "Injury Stoppage", "Half Start", "Half End",
]


class PassDetails(BaseModel):
    recipient: str | None = None
    end_location: Point | None = None
    length: float | None = None  # pitch units
    angle: float | None = None  # radians
    height: str | None = None  # "Ground Pass" | "Low Pass" | "High Pass"
    body_part: str | None = None  # "Right Foot" | "Left Foot" | "Head" | ...
    type: str | None = None  # set piece: "Corner" | "Free Kick" | "Throw-in" | "Goal Kick" | "Kick Off"
    technique: str | None = None  # "Through Ball" | "Inswinging" | ...
    cross: bool = False
    outcome: str = "Complete"  # "Complete" | "Incomplete" | "Out" | "Pass Offside" | ...
    shot_assist: bool = False
    goal_assist: bool = False


class ShotDetails(BaseModel):
    outcome: str  # "Goal" | "Saved" | "Off T" | "Blocked" | "Wayward" | "Post"
    end_location: tuple[float, ...] | None = None  # (x, y) or (x, y, z)
    body_part: str | None = None
    technique: str | None = None  # "Normal" | "Volley" | "Half Volley" | "Lob" | ...
    type: str | None = None  # "Open Play" | "Penalty" | "Free Kick" | "Corner"
    first_time: bool = False
    provider_xg: float | None = None  # the data provider's own xG, if any; we compute our own


class CarryDetails(BaseModel):
    end_location: Point | None = None


class FoulDetails(BaseModel):
    card: str | None = None  # "Yellow Card" | "Second Yellow" | "Red Card"
    penalty: bool = False
    advantage: bool = False


class SubstitutionDetails(BaseModel):
    replacement: str | None = None
    outcome: str | None = None  # "Injury" | "Tactical"


class MatchEvent(BaseModel):
    id: str
    index: int  # order in the match feed
    period: int  # 1, 2 = halves; 3, 4 = extra time; 5 = penalty shootout
    minute: int  # match clock, as shown on TV (keeps counting across halves)
    second: int
    type: EventType
    team: str
    player: str | None = None
    position: str | None = None
    location: Point | None = None
    play_pattern: str | None = None  # "Regular Play" | "From Counter" | "From Corner" | ...
    under_pressure: bool = False
    possession: int | None = None  # id of the possession sequence this event belongs to
    possession_team: str | None = None
    duration: float | None = None  # seconds
    outcome: str | None = None  # generic outcome for duels, dribbles, interceptions...

    pass_: PassDetails | None = Field(default=None, alias="pass")
    shot: ShotDetails | None = None
    carry: CarryDetails | None = None
    foul: FoulDetails | None = None
    substitution: SubstitutionDetails | None = None
    card: str | None = None  # on "Card" events

    model_config = {"populate_by_name": True}

    @property
    def match_seconds(self) -> int:
        return self.minute * 60 + self.second

    @property
    def is_goal(self) -> bool:
        return self.shot is not None and self.shot.outcome == "Goal"


class Player(BaseModel):
    name: str
    jersey_number: int | None = None
    position: str | None = None
    starter: bool = True


class Team(BaseModel):
    name: str
    players: list[Player] = Field(default_factory=list)


class MatchInfo(BaseModel):
    id: str
    home: Team
    away: Team
    competition: str | None = None
    date: str | None = None
    source: str  # "synthetic" | "statsbomb" | "demo"
    extra: dict[str, Any] = Field(default_factory=dict)


class Match(BaseModel):
    info: MatchInfo
    events: list[MatchEvent]
