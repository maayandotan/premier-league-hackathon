"""Turn an event into clear, plain-word fields for the agents.

Lesson from the Caller experiments: structured fields ("passer", "receiver") stop the model
from mixing up who did what, and plain words stop data terms ("Off T") leaking into speech.
"""
from app.events.models import MatchEvent
from app.stats.engine import StatsEngine
from app.stats.geometry import in_box
from app.stats.ranker import Moment

# Data terms -> words a commentator would use. None means "not worth saying".
PLAIN = {
    "Throw-in": "throw-in", "Corner": "corner", "Free Kick": "free kick", "Goal Kick": "goal kick",
    "Kick Off": "kick-off", "High Pass": "long ball", "Low Pass": "low pass", "Ground Pass": None,
    "Through Ball": "through ball", "Inswinging": "inswinging", "Outswinging": "outswinging",
    "Penalty": "penalty", "Open Play": None, "Right Foot": "right foot", "Left Foot": "left foot",
    "Head": "header", "Goal": "goal", "Saved": "saved", "Off T": "off target", "Post": "hits the post",
    "Blocked": "blocked", "Wayward": "off target", "From Counter": "counter-attack",
    "From Corner": "from a corner", "From Free Kick": "from a free kick", "From Throw In": "from a throw-in",
    "Regular Play": "open play",  # said, not left out: a gap got filled with "from a corner"
}


def plain(term: str | None) -> str | None:
    return PLAIN.get(term, term.lower()) if term else None


def zone(event: MatchEvent, flip: bool = False) -> str | None:
    """Where on the pitch, in words, from the acting team's point of view (or the other team's)."""
    if not event.location:
        return None
    x, y = event.location[:2]
    if flip:
        x, y = 120 - x, 80 - y
    if in_box(x, y):
        return "in the box"
    return "final third" if x >= 80 else "midfield" if x >= 40 else "own half"


def score_line(stats: StatsEngine) -> str:
    return f"{stats.home} {stats.score[stats.home]} - {stats.score[stats.away]} {stats.away}"


def event_fields(event: MatchEvent, moment: Moment, stats: StatsEngine) -> dict:
    """The facts about one moment, as labelled fields. Empty values are left out."""
    fields = {
        "minute": event.minute,
        "score": score_line(stats),
        "event": event.type,
        "player": event.player,
        "team": event.team,
        "where": zone(event),
        "play_pattern": plain(event.play_pattern),
    }
    if event.pass_:
        fields.pop("player")
        fields |= {"passer": event.player, "receiver": event.pass_.recipient,
                   "pass_type": plain(event.pass_.technique or event.pass_.type or event.pass_.height)}
    if event.shot:
        fields |= {"shot_type": plain(event.shot.type), "body_part": plain(event.shot.body_part),
                   "outcome": plain(event.shot.outcome)}
    if event.type == "Foul Committed":
        # The event belongs to the team that FOULED. Say who benefits, from their point of view;
        # "team: X, moment: penalty awarded" made the model think X got the penalty.
        other = stats.away if event.team == stats.home else stats.home
        fields.pop("team")
        fields |= {"fouling_team": event.team, "awarded_to": other, "where": zone(event, flip=True)}
        if event.player:
            fields["fouling_player"] = fields.pop("player")
    if event.substitution:
        # "player" on a substitution is the one going OFF; with only that, the Caller said he came on.
        fields.pop("player", None)
        fields |= {"player_off": event.player, "player_on": event.substitution.replacement}
    if card := event.card or (event.foul.card if event.foul else None):
        fields["card"] = card.lower()
        fields["booked_team"] = event.team
    fields["moment"] = moment.reason
    return {key: value for key, value in fields.items() if value is not None}


def as_text(fields: dict) -> str:
    return "\n".join(f"{key}: {value}" for key, value in fields.items())


def ordinal(n: int) -> str:
    """1 -> "1st", 22 -> "22nd": for minutes and league positions."""
    suffix = "th" if 10 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"
