"""The squads of the Meridian League's 20 fictional clubs (DATA_POLICY.md rule 4: nothing real).

Northbridge and Westvale were written by hand for the demo story; the other 18 are generated from
invented surname syllables (seeded, so every run gives the same squads), with a captain each.

Both play a 4-3-3. Each position has a home spot on the pitch, in the team's own attacking
frame (x 0 = own goal line, 120 = opponent's; y 0 = left touchline, 80 = right), so the
simulator can pick the players near the ball.
"""
import random
from dataclasses import dataclass

from app.events.models import Player, Team
from app.league.clubs import CLUB_BY_NAME, CLUBS

NORTHBRIDGE = "Northbridge FC"
WESTVALE = "Westvale United"

# Position name (StatsBomb style) -> home spot (x, y) and line.
FORMATION_433: dict[str, tuple[float, float, str]] = {
    "Goalkeeper": (4, 40, "GK"),
    "Right Back": (32, 70, "DEF"),
    "Right Center Back": (22, 52, "DEF"),
    "Left Center Back": (22, 28, "DEF"),
    "Left Back": (32, 10, "DEF"),
    "Center Defensive Midfield": (45, 40, "MID"),
    "Right Center Midfield": (62, 55, "MID"),
    "Left Center Midfield": (62, 25, "MID"),
    "Right Wing": (92, 70, "FWD"),
    "Left Wing": (92, 10, "FWD"),
    "Center Forward": (100, 40, "FWD"),
}


@dataclass(frozen=True)
class SquadPlayer:
    name: str
    number: int
    position: str  # a starter's position, or the line a substitute plays in ("GK", "DEF", "MID", "FWD")
    starter: bool = True

    @property
    def line(self) -> str:
        return FORMATION_433[self.position][2] if self.position in FORMATION_433 else self.position


def _squad(starters: list[tuple[int, str]], bench: list[tuple[int, str, str]]) -> list[SquadPlayer]:
    players = [SquadPlayer(name, number, position)
               for (number, name), position in zip(starters, FORMATION_433, strict=True)]
    return players + [SquadPlayer(name, number, line, starter=False) for number, name, line in bench]


# Starters in FORMATION_433 order: GK, RB, RCB, LCB, LB, CDM, RCM, LCM, RW, LW, CF.
SQUADS: dict[str, list[SquadPlayer]] = {
    NORTHBRIDGE: _squad(
        [(1, "T. Brannock"), (2, "J. Okafor-Lyle"), (5, "S. Vantreight"), (6, "L. Mburu"), (3, "C. Delacey"),
         (4, "R. Ashdown"), (8, "D. Arlo"), (14, "N. Kestrel"), (7, "E. Sorvino"), (11, "A. Quillan"),
         (10, "M. Ferro")],
        [(13, "P. Gatling", "GK"), (15, "H. Rennick", "DEF"), (22, "O. Tamsin", "DEF"),
         (16, "F. Lowery", "MID"), (18, "B. Achterberg", "MID"), (9, "Z. Okonjo", "FWD"),
         (19, "I. Pellow", "FWD")],
    ),
    WESTVALE: _squad(
        [(1, "G. Marrow"), (2, "A. Fennimore"), (4, "K. Osei"), (5, "V. Darrow"), (3, "Y. Castellan"),
         (6, "W. Thistlewood"), (8, "R. Lindgate"), (10, "T. Calloway"), (7, "S. Abernathy-Roux"),
         (11, "L. Pirozzi"), (9, "C. Dunmore")],
        [(13, "E. Hask", "GK"), (15, "M. Ojukwu", "DEF"), (23, "D. Penhallow", "DEF"),
         (17, "F. Grisedale", "MID"), (20, "U. Sallow", "MID"), (19, "K. Mabry", "FWD"),
         (21, "R. Teague", "FWD")],
    ),
}


# Invented surname syllables: the combinations aren't real players.
_STARTS = ["Ash", "Brin", "Cal", "Dar", "El", "Fen", "Gar", "Hal", "Ivo", "Jas", "Kel", "Lor", "Mor", "Nor",
           "Ol", "Pen", "Quil", "Ral", "Sor", "Tam", "Ul", "Ver", "Wyn", "Yar", "Zel", "Bre", "Cor", "Dun",
           "Fal", "Gil", "Hast", "Kirr", "Lund", "Marr", "Nev", "Orr", "Pell", "Rook", "Stav", "Tor"]
_ENDS = ["ley", "wick", "more", "ford", "ton", "ridge", "dale", "lowe", "sby", "worth", "ard", "ell",
         "ings", "ock", "ett", "ian", "ova", "ez", "ini", "ski", "ani", "berg", "ssen", "oyle", "ane"]
_INITIALS = "ABCDEFGHIJKLMNOPRSTVWY"
_BENCH_LINES = [(13, "GK"), (15, "DEF"), (22, "DEF"), (16, "MID"), (18, "MID"), (19, "FWD"), (21, "FWD")]
_STARTER_NUMBERS = [1, 2, 5, 6, 3, 4, 8, 10, 7, 11, 9]  # in FORMATION_433 order


def _generated_squad(club_name: str, taken: set[str]) -> list[SquadPlayer]:
    rng = random.Random(club_name)
    names: list[str] = []
    while len(names) < 18:
        name = f"{rng.choice(_INITIALS)}. {rng.choice(_STARTS)}{rng.choice(_ENDS)}"
        if name not in taken:
            taken.add(name)
            names.append(name)
    return _squad(list(zip(_STARTER_NUMBERS, names[:11], strict=True)),
                  [(number, name, line)
                   for (number, line), name in zip(_BENCH_LINES, names[11:], strict=True)])


_taken = {p.name for squad in SQUADS.values() for p in squad}
for _club in CLUBS:
    if _club.name not in SQUADS:
        SQUADS[_club.name] = _generated_squad(_club.name, _taken)

CAPTAIN_POSITION = "Center Defensive Midfield"


def captain(club_name: str) -> str:
    """The captain: the holding midfielder, a classic choice (R. Ashdown at Northbridge)."""
    return next(p.name for p in SQUADS[club_name] if p.position == CAPTAIN_POSITION)


def team_info(name: str) -> Team:
    """The squad as it appears in the match file's info."""
    club = CLUB_BY_NAME.get(name)
    return Team(name=name, code=club.code if club else None, color=club.primary if club else None, players=[
        Player(name=p.name, jersey_number=p.number, position=p.position if p.starter else None,
               starter=p.starter)
        for p in SQUADS[name]
    ])
