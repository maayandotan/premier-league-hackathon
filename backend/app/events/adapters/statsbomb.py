"""StatsBomb Open Data -> our Match model. For LOCAL TESTING ONLY (DATA_POLICY.md):
the files live in data/real/ (git-ignored) and nothing derived from them ships.
"""
import json
from pathlib import Path
from typing import Any

from app.events.models import (
    CarryDetails,
    FoulDetails,
    Match,
    MatchEvent,
    MatchInfo,
    PassDetails,
    Player,
    ShotDetails,
    SubstitutionDetails,
    Team,
)

# StatsBomb types we keep under the same name; "Bad Behaviour" becomes "Card".
KEPT_TYPES = {
    "Pass", "Carry", "Shot", "Dribble", "Duel", "Interception", "Ball Recovery", "Clearance",
    "Block", "Pressure", "Foul Committed", "Foul Won", "Offside", "Substitution", "Goal Keeper",
    "Miscontrol", "Dispossessed", "Injury Stoppage", "Half Start", "Half End",
}


def _name(obj: dict | None) -> str | None:
    return obj.get("name") if obj else None


def _point(value: list | None) -> tuple[float, ...] | None:
    return tuple(value) if value else None


def to_event(raw: dict[str, Any]) -> MatchEvent | None:
    """Convert one StatsBomb event, or return None for types we don't use."""
    sb_type = raw["type"]["name"]
    if sb_type == "Bad Behaviour":
        event_type = "Card"
    elif sb_type in KEPT_TYPES:
        event_type = sb_type
    else:
        return None

    fields: dict[str, Any] = {}
    if p := raw.get("pass"):
        fields["pass"] = PassDetails(
            recipient=_name(p.get("recipient")),
            end_location=_point(p.get("end_location")),
            length=p.get("length"),
            angle=p.get("angle"),
            height=_name(p.get("height")),
            body_part=_name(p.get("body_part")),
            type=_name(p.get("type")),
            technique=_name(p.get("technique")),
            cross=p.get("cross", False),
            outcome=_name(p.get("outcome")) or "Complete",  # StatsBomb omits the outcome on completed passes
            shot_assist=p.get("shot_assist", False),
            goal_assist=p.get("goal_assist", False),
        )
    if s := raw.get("shot"):
        fields["shot"] = ShotDetails(
            outcome=_name(s.get("outcome")) or "Unknown",
            end_location=_point(s.get("end_location")),
            body_part=_name(s.get("body_part")),
            technique=_name(s.get("technique")),
            type=_name(s.get("type")),
            first_time=s.get("first_time", False),
            provider_xg=s.get("statsbomb_xg"),
        )
    if c := raw.get("carry"):
        fields["carry"] = CarryDetails(end_location=_point(c.get("end_location")))
    if f := raw.get("foul_committed"):
        fields["foul"] = FoulDetails(
            card=_name(f.get("card")), penalty=f.get("penalty", False), advantage=f.get("advantage", False)
        )
    if sub := raw.get("substitution"):
        fields["substitution"] = SubstitutionDetails(
            replacement=_name(sub.get("replacement")), outcome=_name(sub.get("outcome"))
        )
    if b := raw.get("bad_behaviour"):
        fields["card"] = _name(b.get("card"))
    for key in ("duel", "dribble", "interception"):
        if outcome := _name((raw.get(key) or {}).get("outcome")):
            fields["outcome"] = outcome

    return MatchEvent(
        id=raw["id"],
        index=raw["index"],
        period=raw["period"],
        minute=raw["minute"],
        second=raw["second"],
        type=event_type,
        team=raw["team"]["name"],
        player=_name(raw.get("player")),
        position=_name(raw.get("position")),
        location=_point(raw.get("location")),
        play_pattern=_name(raw.get("play_pattern")),
        under_pressure=raw.get("under_pressure", False),
        possession=raw.get("possession"),
        possession_team=_name(raw.get("possession_team")),
        duration=raw.get("duration"),
        **fields,
    )


def to_events(raw_events: list[dict[str, Any]]) -> list[MatchEvent]:
    events = [e for raw in raw_events if (e := to_event(raw)) is not None]
    return sorted(events, key=lambda e: e.index)


def _team(raw_lineup: dict[str, Any]) -> Team:
    players = []
    for p in raw_lineup.get("lineup", []):
        positions = p.get("positions") or []
        players.append(Player(
            name=p["player_name"],  # same name the events use
            jersey_number=p.get("jersey_number"),
            position=positions[0]["position"] if positions else None,
            starter=any(pos.get("start_reason") == "Starting XI" for pos in positions),
        ))
    return Team(name=raw_lineup["team_name"], players=players)


def load_match(data_dir: Path, match_id: str) -> Match:
    """Load events_<id>.json and lineups_<id>.json (and match info from matches_*.json if present)."""
    raw_events = json.loads((data_dir / f"events_{match_id}.json").read_text())
    events = to_events(raw_events)

    lineups_path = data_dir / f"lineups_{match_id}.json"
    lineups = json.loads(lineups_path.read_text()) if lineups_path.exists() else []
    teams = {t["team_name"]: _team(t) for t in lineups}

    info: dict[str, Any] = {}
    for matches_file in data_dir.glob("matches_*.json"):
        for m in json.loads(matches_file.read_text()):
            if str(m["match_id"]) == str(match_id):
                info = m
    home_name = (info.get("home_team") or {}).get("home_team_name") or events[0].team
    away_name = (info.get("away_team") or {}).get("away_team_name") or next(
        e.team for e in events if e.team != home_name
    )
    return Match(
        info=MatchInfo(
            id=str(match_id),
            home=teams.get(home_name, Team(name=home_name)),
            away=teams.get(away_name, Team(name=away_name)),
            competition=(info.get("competition") or {}).get("competition_name"),
            date=info.get("match_date"),
            source="statsbomb",
        ),
        events=events,
    )
