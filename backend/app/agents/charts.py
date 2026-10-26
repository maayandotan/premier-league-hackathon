"""Charts that come with an answer: "what happens when Northbridge score two or more?", "does Ferro
score late?", "how did the chances build up?".

Code builds every chart from the data; the model only decides that one is wanted, by calling a
show_ tool in qa.py. Each builder returns two things:
- words for the model: the same numbers the chart shows, with how many matches or shots they come
  from (one season so far is a small sample, and the answer should say so);
- a chart spec for the page: data only, no sentences, so the page can label it in the viewer's
  language.
The spec rides on the answer's CommentaryLine (`chart`), collected here per question like the
checker collects tool results.
"""
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from contextvars import ContextVar

from app.events.models import MatchEvent
from app.league.db import league
from app.stats.ranker import Moment
from app.stats.xg import shot_xg

WINDOWS = ((0, 15), (15, 30), (30, 45), (45, 60), (60, 75), (75, 200))  # the last one includes added time
WINDOW_LABELS = ["0-15'", "15-30'", "30-45'", "45-60'", "60-75'", "75-90'+"]

_charts: ContextVar[list[dict] | None] = ContextVar("charts", default=None)


@contextmanager
def charting() -> Iterator[list[dict]]:
    """Collect the charts one question's tools made."""
    made: list[dict] = []
    token = _charts.set(made)
    try:
        yield made
    finally:
        _charts.reset(token)


def _show(chart: dict) -> None:
    if (made := _charts.get()) is not None:
        made.append(chart)


def _window(minute: int) -> int:
    return next(i for i, (start, end) in enumerate(WINDOWS) if start <= minute < end)


def team_results_by_goals(team: str) -> dict:
    """A club's league results grouped by how many goals it scored: 0, 1, 2, 3 or more."""
    games = league().team_scores(team)
    groups = ["0", "1", "2", "3+"]
    counts = {g: {"won": 0, "drawn": 0, "lost": 0} for g in groups}
    for scored, conceded in games:
        result = "won" if scored > conceded else "drawn" if scored == conceded else "lost"
        counts[groups[min(scored, 3)]][result] += 1
    two_plus = {key: counts["2"][key] + counts["3+"][key] for key in ("won", "drawn", "lost")}
    _show({"type": "team_by_goals", "team": team, "matches": len(games), "groups": groups,
           "won": [counts[g]["won"] for g in groups], "drawn": [counts[g]["drawn"] for g in groups],
           "lost": [counts[g]["lost"] for g in groups]})
    return {"team": team, "league_matches_so_far": len(games),
            "results_by_goals_scored": {f"scored {g}": counts[g] for g in groups},
            "when_scoring_2_or_more": two_plus,
            "sample": f"{len(games)} league matches this season: a small sample, say so"}


def player_scoring_by_time(player: str) -> dict:
    """A player's league shots and goals by 15-minute window, and his penalties with their minutes."""
    shots = league().player_shots(player)
    taken = [0] * len(WINDOWS)
    scored = [0] * len(WINDOWS)
    for minute, goal, _ in shots:
        taken[_window(minute)] += 1
        scored[_window(minute)] += goal
    penalties = [{"minute": minute, "scored": goal} for minute, goal, penalty in shots if penalty]
    _show({"type": "player_by_time", "player": player, "windows": WINDOW_LABELS, "shots": taken,
           "goals": scored, "penalties": penalties})
    early, late = sum(taken[:3]), sum(taken[3:])
    def rate(goals: int, attempts: int) -> str:
        return f"{round(100 * goals / attempts)}%" if attempts else "no shots"

    windows = zip(WINDOW_LABELS, taken, scored, strict=True)
    return {"player": player, "league_shots": len(shots), "league_goals": sum(scored),
            "by_window": {label: {"shots": s, "goals": g} for label, s, g in windows},
            "first_half_conversion": rate(sum(scored[:3]), early),
            "second_half_conversion": rate(sum(scored[3:]), late),
            "windows": "15-minute windows; the last one is the last 15 minutes plus added time",
            "last_15_minutes_conversion": rate(scored[-1], taken[-1]),
            "penalties": {"taken": len(penalties), "scored": sum(p["scored"] for p in penalties),
                          "minutes": [f"{p['minute']}' {'scored' if p['scored'] else 'missed'}"
                                      for p in penalties]},
            "sample": f"{len(shots)} shots this season: a small sample, say so"}


def xg_race(timeline: Sequence[tuple[MatchEvent, Moment]], home: str, away: str) -> dict:
    """This match: each team's expected goals adding up, minute by minute, with the goals marked."""
    totals = {home: 0.0, away: 0.0}
    points = {home: [[0, 0.0]], away: [[0, 0.0]]}
    goals = []
    for event, _ in timeline:
        if event.shot is not None and event.period < 5 and event.team in totals:
            totals[event.team] += shot_xg(event) or 0
            points[event.team].append([event.minute, round(totals[event.team], 2)])
            if event.is_goal:
                goals.append({"team": event.team, "minute": event.minute})
    minute = timeline[-1][0].minute if timeline else 0
    for team in totals:  # carry each line to the current minute
        points[team].append([minute, round(totals[team], 2)])
    _show({"type": "xg_race", "home": home, "away": away, "points": points, "goals": goals, "minute": minute})
    return {"xg_so_far": {team: round(xg, 2) for team, xg in totals.items()}, "minute": minute,
            "goals": [f"{g['team']} {g['minute']}'" for g in goals]}
