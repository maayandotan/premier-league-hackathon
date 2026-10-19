"""A tiny hand-written match moment so the skeleton runs end to end before the
generator exists. Fictional teams and players only (DATA_POLICY.md)."""
from app.events.models import MatchEvent

DEMO_EVENTS = [
    MatchEvent(id="d1", period=2, minute=60, second=30, type="Pass", team="Northbridge FC",
               player="D. Arlo", location=(50.0, 23.0), details={"recipient": "M. Ferro"}),
    MatchEvent(id="d2", period=2, minute=60, second=33, type="Carry", team="Northbridge FC",
               player="M. Ferro", location=(78.0, 30.0)),
    MatchEvent(id="d3", period=2, minute=60, second=36, type="Shot", team="Northbridge FC",
               player="M. Ferro", location=(104.0, 36.0), details={"outcome": "Goal", "xg": 0.09}),
    MatchEvent(id="d4", period=2, minute=61, second=10, type="Foul Committed", team="Westvale United",
               player="K. Osei", location=(60.0, 50.0)),
]
