"""The Meridian League: clubs, squads, fixtures, the season, the results database and its API."""
from collections import Counter

from fastapi.testclient import TestClient

from app.league.clubs import CLUBS
from app.league.db import League
from app.league.season import (
    CURRENT_ROUND,
    FEATURED,
    PLAYED,
    fixture_source,
    fixtures,
    load_season,
    play,
    summarize,
)
from app.main import app
from app.synthetic.squads import SQUADS, captain

client = TestClient(app)


def test_twenty_fictional_clubs_with_full_squads_and_captains():
    assert len(CLUBS) == 20 and len({c.code for c in CLUBS}) == 20
    names = [p.name for club in CLUBS for p in SQUADS[club.name]]
    assert len(names) == 20 * 18 and len(set(names)) == len(names)  # nobody plays for two clubs
    assert all(sum(p.starter for p in SQUADS[c.name]) == 11 for c in CLUBS)
    assert captain("Northbridge FC") == "R. Ashdown"


def test_a_proper_double_round_robin():
    rounds = fixtures()
    assert len(rounds) == 38 and all(len(matchday) == 10 for matchday in rounds)
    for matchday in rounds:  # everyone plays once a matchday
        assert len({team for pair in matchday for team in pair}) == 20
    pairs = Counter(pair for matchday in rounds for pair in matchday)
    assert len(pairs) == 20 * 19 and set(pairs.values()) == {1}  # each pairing once at home, once away
    assert FEATURED in rounds[CURRENT_ROUND - 1]


def test_the_saved_season_matches_the_fixtures_and_the_generator():
    season = load_season()
    assert season["played"] == PLAYED and len(season["results"]) == PLAYED * 10
    first = season["results"][0]
    home, away = fixtures()[0][0]
    assert (first["home"], first["away"]) == (home, away)
    assert summarize(play(1, home, away), 1) == first  # same fixture, same match


def test_the_table_adds_up():
    table = League().table()
    assert [row["position"] for row in table] == list(range(1, 21))
    assert all(row["played"] == PLAYED for row in table)
    assert all(row["points"] == 3 * row["won"] + row["drawn"] for row in table)
    assert sum(row["goal_difference"] for row in table) == 0
    order = sorted(table, key=lambda r: (-r["points"], -r["goal_difference"], -r["goals_for"], r["team"]))
    assert table == order


def test_a_watched_match_counts_once():
    lg = League()
    home, away = fixtures()[CURRENT_ROUND - 1][0]
    result = summarize(play(CURRENT_ROUND, home, away), CURRENT_ROUND)
    assert lg.record(result) and not lg.record(result)  # watching it twice counts once
    row = next(r for r in lg.table() if r["team"] == home)
    assert row["played"] == PLAYED + 1
    assert next(f for f in lg.todays_fixtures() if f["home"] == home)["result"] == \
        f"{result['home_goals']}-{result['away_goals']}"


def test_a_clubs_season():
    club = League().club("Northbridge FC")
    assert club["captain"] == "R. Ashdown" and club["played"] == PLAYED
    assert club["top_scorers"] and all(s["goals"] >= 1 for s in club["top_scorers"])


def test_league_api_and_fixture_sources():
    league = client.get("/api/league").json()
    assert league["matchday"] == CURRENT_ROUND
    assert len(league["table"]) == 20 and len(league["fixtures"]) == 10
    featured = next(f for f in league["fixtures"] if (f["home"], f["away"]) == FEATURED)
    assert featured["source"] == "synthetic:comeback"
    other = next(f for f in league["fixtures"] if (f["home"], f["away"]) != FEATURED)
    assert other["source"] == fixture_source(other["home"], other["away"])
    info = client.get(f"/api/match-info?source={other['source']}").json()
    assert (info["home"]["name"], info["away"]["name"]) == (other["home"], other["away"])
    assert info["home"]["code"] and info["home"]["color"].startswith("#")
    assert client.get("/api/league/club?name=Nowhere FC").status_code == 404
    assert client.get("/api/match-info?source=fixture:NOR-RED").status_code == 404  # not today's fixture
