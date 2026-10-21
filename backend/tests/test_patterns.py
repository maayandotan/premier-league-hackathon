"""The Tactical Intelligence Engine (#48): patterns from event locations and timing."""
from app.events.models import CarryDetails, MatchEvent, PassDetails, ShotDetails
from app.stats.engine import StatsEngine
from app.stats.patterns import channel
from app.synthetic.scenarios import SCENARIOS
from app.synthetic.simulator import generate_match

HOME, AWAY = "Northbridge FC", "Westvale United"
_n = iter(range(1, 10_000))


def event(minute, type_, team=HOME, location=(50.0, 40.0), possession=1, second=0, **fields):
    i = next(_n)
    return MatchEvent(id=f"e{i}", index=i, period=2, minute=minute, second=second, type=type_, team=team,
                      location=location, possession=possession, **fields)


def entry(minute, y, team=HOME, possession=1):
    """A completed pass into the final third, ending at height y."""
    return event(minute, "Pass", team, (70.0, y), possession, **{"pass": PassDetails(end_location=(85.0, y))})


def engine(*events) -> StatsEngine:
    stats = StatsEngine(HOME, AWAY)
    for e in events:
        stats.update(e)
    return stats


def test_channels_are_from_the_attacking_teams_view():
    assert (channel(5), channel(40), channel(75)) == ("left", "centre", "right")


def test_a_team_that_keeps_going_down_the_right():
    stats = engine(*[entry(60 + i, 70.0, possession=i) for i in range(6)], entry(67, 40.0, possession=9))
    assert stats.patterns.main_channel(HOME) == ("right", 6, 7)
    assert "6 of 7 final-third entries down the right in the last 15 minutes" in stats.patterns.patterns(HOME)


def test_no_pattern_without_enough_of_it():
    stats = engine(*[entry(60 + i, 70.0, possession=i) for i in range(4)])
    assert stats.patterns.main_channel(HOME) is None  # 4 entries is not a habit
    summary = stats.patterns.summary()[HOME]
    assert summary["last_15_minutes"] == ["no clear pattern in the last 15 minutes"]
    assert summary["final_third_entries_all_match"] == {"left": 0, "centre": 0, "right": 4}


def test_old_entries_drop_out_of_the_window():
    early = [entry(10 + i, 70.0, possession=i) for i in range(6)]
    stats = engine(*early, event(40, "Pass", location=(30.0, 40.0)))
    assert stats.patterns.main_channel(HOME) is None


def test_pressing_high_is_balls_won_in_the_opponents_half():
    wins = [event(60, "Ball Recovery", location=(75.0, 40.0), possession=i, second=i) for i in range(6)]
    stats = engine(*wins, event(61, "Interception", AWAY, (70.0, 40.0), outcome="Won"))
    assert any("won the ball 6 times in the opponent's half" in p for p in stats.patterns.patterns(HOME))


def test_a_transition_is_a_shot_soon_after_winning_the_ball():
    attacks = []
    for i in range(3):
        attacks += [event(60 + i, "Interception", location=(40.0, 40.0), possession=10 + i, outcome="Won"),
                    event(60 + i, "Carry", location=(40.0, 40.0), possession=10 + i, second=4,
                          carry=CarryDetails(end_location=(104.0, 40.0)))]
    stats = engine(*attacks)
    assert any("3 quick attacks straight after winning the ball" in p for p in stats.patterns.patterns(HOME))


def test_a_goal_down_the_usual_side_pays_off_the_pattern():
    build_up = [entry(60 + i, 70.0, possession=i) for i in range(6)] + [entry(67, 40.0, possession=7)]
    goal_attack = entry(70, 70.0, possession=8)
    goal = event(70, "Shot", location=(108.0, 40.0), possession=8, second=5, shot=ShotDetails(outcome="Goal"))
    stats = engine(*build_up, goal_attack, goal)
    assert stats.patterns.goal_route(goal) == \
        "came down the right, their most-used side: 7 of their 8 final-third entries this match"


def test_generated_styles_show_up_and_neutral_matches_stay_quiet():
    """The comeback's Northbridge attack down the right and Westvale press; the open match has no style."""
    def fired(name, team, words):
        hits = checks = 0
        for seed in range(4):
            match = generate_match(SCENARIOS[name], seed)
            stats, next_check = StatsEngine(HOME, AWAY), 20 * 60
            for e in match.events:
                stats.update(e)
                if e.match_seconds >= next_check:
                    next_check += 5 * 60
                    checks += 1
                    hits += any(words in p for p in stats.patterns.patterns(team))
        return hits / checks

    assert fired("comeback", HOME, "down the right") > 0.25
    assert fired("comeback", AWAY, "opponent's half") > 0.2
    assert fired("open", HOME, "down the right") < 0.1
