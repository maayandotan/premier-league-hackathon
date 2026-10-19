"""A short hand-written match moment so the app runs end to end without any data files.
Fictional teams and players only (DATA_POLICY.md). Also exported as data/synthetic/sample_match.json."""
from app.events.models import (
    CarryDetails,
    FoulDetails,
    Match,
    MatchEvent,
    MatchInfo,
    PassDetails,
    Player,
    ShotDetails,
    Team,
)

NORTHBRIDGE = "Northbridge FC"
WESTVALE = "Westvale United"


def _e(index: int, minute: int, second: int, type_: str, team: str, **fields) -> MatchEvent:
    return MatchEvent(id=f"demo-{index}", index=index, period=2, minute=minute, second=second,
                      type=type_, team=team, **fields)


DEMO_MATCH = Match(
    info=MatchInfo(
        id="demo",
        source="demo",
        competition="Demo",
        home=Team(name=NORTHBRIDGE, players=[
            Player(name="D. Arlo", jersey_number=8, position="Center Midfield"),
            Player(name="M. Ferro", jersey_number=10, position="Center Forward"),
        ]),
        away=Team(name=WESTVALE, players=[
            Player(name="K. Osei", jersey_number=4, position="Center Back"),
            Player(name="L. Brandt", jersey_number=1, position="Goalkeeper"),
        ]),
    ),
    events=[
        _e(1, 60, 30, "Pass", NORTHBRIDGE, player="D. Arlo", position="Center Midfield",
           location=(50.0, 23.0), play_pattern="From Counter", under_pressure=True, possession=1,
           possession_team=NORTHBRIDGE,
           **{"pass": PassDetails(recipient="M. Ferro", end_location=(78.0, 30.0), length=28.9,
                                  height="Ground Pass", body_part="Right Foot", technique="Through Ball",
                                  shot_assist=True, goal_assist=True)}),
        _e(2, 60, 33, "Carry", NORTHBRIDGE, player="M. Ferro", position="Center Forward",
           location=(78.0, 30.0), play_pattern="From Counter", possession=1, possession_team=NORTHBRIDGE,
           carry=CarryDetails(end_location=(102.0, 36.0))),
        _e(3, 60, 36, "Shot", NORTHBRIDGE, player="M. Ferro", position="Center Forward",
           location=(102.0, 36.0), play_pattern="From Counter", possession=1, possession_team=NORTHBRIDGE,
           shot=ShotDetails(outcome="Goal", end_location=(120.0, 38.0, 1.2), body_part="Left Foot",
                            technique="Normal", type="Open Play")),
        _e(4, 61, 10, "Foul Committed", WESTVALE, player="K. Osei", position="Center Back",
           location=(60.0, 50.0), possession=2, possession_team=NORTHBRIDGE,
           foul=FoulDetails(card="Yellow Card")),
    ],
)
