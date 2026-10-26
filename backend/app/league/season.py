"""The Meridian League season: 38 matchdays, the ones already played, and today's matchday.

Matchdays 1 to PLAYED are played by the synthetic generator (each club's strength and style from
clubs.py) and saved to data/synthetic/league/season.json by scripts/build_league.py, so the app
starts with a real table instead of simulating 100 matches. Matchday CURRENT_ROUND is "today":
any of its fixtures can be watched, and the featured one is the scripted comeback.
"""
import json
import random
import zlib

from app.config import REPO_ROOT
from app.events.models import Match
from app.league.clubs import CLUB_BY_CODE, CLUB_BY_NAME, CLUBS, LEAGUE_NAME
from app.stats.xg import shot_xg
from app.synthetic.scenarios import Scenario, Style
from app.synthetic.simulator import generate_match

PLAYED = 10
CURRENT_ROUND = PLAYED + 1
FEATURED = ("Northbridge FC", "Westvale United")  # today's big game: the demo's scripted comeback
FEATURED_SOURCE = "synthetic:comeback"
SEASON_FILE = REPO_ROOT / "data" / "synthetic" / "league" / "season.json"


def fixtures() -> list[list[tuple[str, str]]]:
    """A double round robin (the circle method): 38 matchdays of (home, away), every pair twice."""
    teams = [club.name for club in CLUBS]
    random.Random("meridian fixtures").shuffle(teams)
    n, rounds = len(teams), []
    for r in range(n - 1):
        pairs = [(teams[i], teams[n - 1 - i]) for i in range(n // 2)]
        rounds.append([(a, b) if (r + i) % 2 == 0 else (b, a) for i, (a, b) in enumerate(pairs)])
        teams = [teams[0], teams[-1], *teams[1:-1]]
    rounds += [[(b, a) for a, b in matchday] for matchday in rounds]
    featured = next(i for i, matchday in enumerate(rounds) if FEATURED in matchday)
    rounds[featured], rounds[CURRENT_ROUND - 1] = rounds[CURRENT_ROUND - 1], rounds[featured]
    return rounds


def match_id(round_no: int, home: str, away: str) -> str:
    return f"r{round_no}-{CLUB_BY_NAME[home].code}-{CLUB_BY_NAME[away].code}"


def scenario_for(home: str, away: str) -> Scenario:
    h, a = CLUB_BY_NAME[home], CLUB_BY_NAME[away]
    return Scenario(name=f"{h.code}-{a.code}", description="", home=home, away=away,
                    home_strength=h.strength, away_strength=a.strength,
                    home_style=Style(channel=h.channel, press=h.press),
                    away_style=Style(channel=a.channel, press=a.press))


def play(round_no: int, home: str, away: str) -> Match:
    """A fixture's match. Same fixture, same match: the seed comes from the fixture."""
    mid = match_id(round_no, home, away)
    return generate_match(scenario_for(home, away), seed=zlib.crc32(mid.encode()), match_id=mid)


def summarize(match: Match, round_no: int) -> dict:
    """What the league keeps of a match: the score, who scored and assisted, the cards, and every
    shot (for "does he score late?" kinds of questions)."""
    home, away = match.info.home.name, match.info.away.name
    goals, cards, shots, last_pass = [], [], [], {}
    for event in match.events:
        if event.pass_ is not None and event.pass_.outcome == "Complete":
            last_pass[event.team] = event
        if event.is_goal and event.period < 5:
            assist = last_pass.get(event.team)
            assister = assist.player if assist and assist.pass_.goal_assist else None
            goals.append({"minute": event.minute, "team": event.team, "scorer": event.player,
                          "assister": assister, "penalty": event.shot.type == "Penalty"})
        if event.shot is not None and event.period < 5:
            shots.append({"minute": event.minute, "team": event.team, "player": event.player,
                          "goal": event.is_goal, "penalty": event.shot.type == "Penalty",
                          "xg": round(shot_xg(event) or 0, 3)})
        card = event.foul.card if event.foul else event.card
        if card:
            cards.append({"minute": event.minute, "team": event.team, "player": event.player, "card": card})
    return {"id": match_id(round_no, home, away), "round": round_no, "home": home, "away": away,
            "home_goals": sum(g["team"] == home for g in goals),
            "away_goals": sum(g["team"] == away for g in goals), "goals": goals, "cards": cards,
            "shots": shots}


def build_season() -> dict:
    """Play matchdays 1..PLAYED (about 100 matches): what scripts/build_league.py saves."""
    rounds = fixtures()
    results = [summarize(play(r, home, away), r)
               for r in range(1, PLAYED + 1) for home, away in rounds[r - 1]]
    return {"league": LEAGUE_NAME, "played": PLAYED, "fixtures": rounds, "results": results}


def load_season() -> dict:
    return json.loads(SEASON_FILE.read_text())


def fixture_source(home: str, away: str) -> str:
    """The match source for one of today's fixtures."""
    if (home, away) == FEATURED:
        return FEATURED_SOURCE
    return f"fixture:{CLUB_BY_NAME[home].code}-{CLUB_BY_NAME[away].code}"


def todays_fixture(codes: str) -> tuple[str, str] | None:
    """'NOR-WEU' -> (home, away) if it's a fixture on today's matchday."""
    home_code, _, away_code = codes.partition("-")
    home, away = CLUB_BY_CODE.get(home_code), CLUB_BY_CODE.get(away_code)
    if home and away and (home.name, away.name) in fixtures()[CURRENT_ROUND - 1]:
        return home.name, away.name
    return None
