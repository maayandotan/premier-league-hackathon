"""The Meridian League: 20 fictional clubs (DATA_POLICY.md rule 4: nothing real).

Invented names (not real towns with real clubs), our own colours and crests, and a style of play
each so the tactical detectors have something real to find. Plain data: the squads are built from
it in app/synthetic/squads.py.
"""
from dataclasses import dataclass
from typing import Literal

LEAGUE_NAME = "Meridian League"


@dataclass(frozen=True)
class Club:
    name: str
    code: str  # 3 letters, like a TV scorebug
    primary: str  # the club colour (hex): the UI takes it when this is the viewer's team
    secondary: str
    strength: float  # 0-1, how good on the ball (the simulator's nudge)
    channel: Literal["left", "right"] | None = None  # the side it keeps attacking down
    press: bool = False  # wins the ball high up the pitch


CLUBS: list[Club] = [
    Club("Northbridge FC", "NOR", "#3b82f6", "#f8fafc", 0.56, channel="right"),
    Club("Westvale United", "WEU", "#f43f5e", "#f8fafc", 0.55, press=True),
    Club("Calderbrook City", "CAL", "#0ea5e9", "#0c4a6e", 0.6, channel="left", press=True),
    Club("Redmarsh Rovers", "RED", "#dc2626", "#111827", 0.52, press=True),
    Club("Oakhaven Athletic", "OAK", "#16a34a", "#f8fafc", 0.5),
    Club("Elmsworth Town", "ELM", "#facc15", "#1e3a8a", 0.47, channel="left"),
    Club("Brackenhill United", "BRA", "#7c3aed", "#f8fafc", 0.53),
    Club("Silverford FC", "SIL", "#94a3b8", "#0f172a", 0.58, channel="right"),
    Club("Ravensmoor FC", "RAV", "#1f2937", "#f59e0b", 0.49, press=True),
    Club("Highcastle Wanderers", "HIG", "#b91c1c", "#facc15", 0.51, channel="left"),
    Club("Larkspur Rangers", "LAR", "#2563eb", "#fde047", 0.46),
    Club("Fenwood Rangers", "FEN", "#15803d", "#facc15", 0.45, channel="right"),
    Club("Ironvale City", "IRO", "#475569", "#f97316", 0.54, press=True),
    Club("Glenmere United", "GLE", "#0d9488", "#f8fafc", 0.48),
    Club("Ashcombe Athletic", "ASH", "#ea580c", "#1c1917", 0.5, channel="right"),
    Club("Saltmarsh FC", "SAL", "#0891b2", "#f8fafc", 0.44),
    Club("Hollowmere Town", "HOL", "#a16207", "#f8fafc", 0.43, channel="left"),
    Club("Whitecliff Rovers", "WHI", "#e2e8f0", "#1e40af", 0.52, press=True),
    Club("Brindleford City", "BRI", "#be185d", "#f8fafc", 0.47),
    Club("Copperfield United", "COP", "#b45309", "#1f2937", 0.5, channel="right", press=True),
]
CLUB_BY_NAME = {club.name: club for club in CLUBS}
CLUB_BY_CODE = {club.code: club for club in CLUBS}
