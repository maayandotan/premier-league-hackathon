"""Charts that come with an answer: built by code from the data, attached to the answer that showed them."""
import asyncio
from types import SimpleNamespace

from app.agents import charts
from app.agents.qa import QuestionAnswerer
from app.agents.viewer import ViewerProfile
from app.league.db import League, league
from app.match.sources import load_source
from app.stats.engine import StatsEngine
from app.stats.ranker import Moment

HOME, AWAY = "Northbridge FC", "Westvale United"


def test_a_clubs_results_by_goals_scored_add_up():
    with charts.charting() as made:
        words = charts.team_results_by_goals(HOME)
    chart = made[0]
    games = league().team_scores(HOME)
    assert chart["type"] == "team_by_goals"
    assert chart["matches"] == len(games) == words["league_matches_so_far"]
    assert sum(chart["won"]) + sum(chart["drawn"]) + sum(chart["lost"]) == len(games)
    wins_scoring_two_plus = sum(1 for scored, conceded in games if scored >= 2 and scored > conceded)
    assert words["when_scoring_2_or_more"]["won"] == wins_scoring_two_plus
    assert "small sample" in words["sample"]  # the answer must say how much data it's from


def test_a_players_scoring_by_match_time_adds_up():
    player = "C. Dunmore"
    shots = League().player_shots(player)
    with charts.charting() as made:
        words = charts.player_scoring_by_time(player)
    chart = made[0]
    assert sum(chart["shots"]) == len(shots) == words["league_shots"]
    assert sum(chart["goals"]) == sum(goal for _, goal, _ in shots) == words["league_goals"]
    assert len(chart["penalties"]) == words["penalties"]["taken"] == sum(pen for *_, pen in shots)


def test_the_league_has_realistic_penalties():
    taken, scored = League()._db.execute("SELECT SUM(penalty), SUM(penalty * goal) FROM shots").fetchone()
    matches = League()._db.execute("SELECT COUNT(*) FROM results").fetchone()[0]
    assert 0.15 <= taken / matches <= 0.5  # real football: about 0.3 a match
    assert 0.6 <= scored / taken <= 0.95  # and about three in four go in


def test_the_xg_race_ends_where_the_stats_engine_is():
    match = load_source("synthetic:comeback")
    stats = StatsEngine(HOME, AWAY)
    timeline = []
    for event in match.events:
        stats.update(event)
        timeline.append((event, Moment(score=0, reason="", kind="routine", quiet=False)))
    with charts.charting() as made:
        words = charts.xg_race(timeline, HOME, AWAY)
    for team in (HOME, AWAY):
        assert words["xg_so_far"][team] == round(stats.xg[team], 2) == made[0]["points"][team][-1][1]
    assert len(made[0]["goals"]) == sum(stats.score.values())


def test_no_chart_outside_a_question():
    charts.team_results_by_goals(HOME)  # a tool called with nobody collecting: nothing breaks


def test_the_answer_carries_the_chart_its_tool_showed():
    class ShowsAChart:
        async def run(self, prompt, **_):
            charts.team_results_by_goals(HOME)  # what the model's tool call does
            return SimpleNamespace(text="Here is how Northbridge have done this season.")

    qa = QuestionAnswerer(StatsEngine(HOME, AWAY), [], {}, use_model=False)
    qa.agent = ShowsAChart()
    text, extras = asyncio.run(qa.answer_with_extras("What happens when we score 2?", 10, 0, ViewerProfile()))
    chart = extras["chart"]
    assert text.startswith("Here is how") and chart["type"] == "team_by_goals" and chart["team"] == HOME

    qa.agent = SimpleNamespace(run=lambda *a, **k: asyncio.sleep(0, SimpleNamespace(text="Level at 0-0.")))
    assert asyncio.run(qa.answer_with_extras("Score?", 10, 0, ViewerProfile()))[1]["chart"] is None  # no tool
