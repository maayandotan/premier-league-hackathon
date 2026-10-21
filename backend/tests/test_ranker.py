from app.events.models import FoulDetails, MatchEvent, PassDetails, ShotDetails
from app.stats.engine import StatsEngine
from app.stats.ranker import rank

HOME, AWAY = "Northbridge FC", "Westvale United"
_index = iter(range(1, 10_000))


def ev(type_, team=HOME, minute=30, period=1, location=(60.0, 40.0), **fields):
    return MatchEvent(id=f"e{next(_index)}", index=next(_index), period=period, minute=minute, second=0,
                      type=type_, team=team, location=location, **fields)


def goal(team=HOME, minute=30, **shot_fields):
    return ev("Shot", team=team, minute=minute, location=(110.0, 40.0),
              shot=ShotDetails(outcome="Goal", **shot_fields))


def ranked(stats, event, momentum_before=None):
    stats.update(event)
    return rank(event, stats, momentum_before)


def test_goals_score_10_with_the_right_story():
    stats = StatsEngine(HOME, AWAY)
    assert ranked(stats, goal()).reason == "go-ahead goal"
    assert ranked(stats, goal()).reason == "extends the lead"
    assert ranked(stats, goal(team=AWAY)).reason == "pulls one back"
    late = ranked(stats, goal(team=AWAY, minute=88))
    assert late.score == 10 and late.reason == "late equalizer" and late.quiet


def test_goal_against_the_run_of_play_and_penalties():
    stats = StatsEngine(HOME, AWAY)
    moment = ranked(stats, goal(type="Penalty"), momentum_before=-0.6)  # away were on top
    assert moment.reason == "penalty go-ahead goal, against the run of play"


def test_shots_ranked_by_chance_quality():
    stats = StatsEngine(HOME, AWAY)
    close = ranked(stats, ev("Shot", location=(114.0, 40.0), shot=ShotDetails(outcome="Saved")))
    far = ranked(stats, ev("Shot", location=(88.0, 40.0), shot=ShotDetails(outcome="Off T")))
    assert close.score > far.score
    assert close.reason == "big chance, saved"
    assert far.reason == "speculative effort"


def test_cards_and_fouls():
    stats = StatsEngine(HOME, AWAY)
    assert ranked(stats, ev("Card", card="Red Card")).reason == "sent off"
    assert ranked(stats, ev("Foul Committed", foul=FoulDetails(penalty=True))).score == 9
    # Fouling team's coordinates: x near 0 is their own goal, so this is in shooting range
    assert ranked(stats, ev("Foul Committed", location=(25.0, 40.0))).reason == "free kick in shooting range"
    midfield = ranked(stats, ev("Foul Committed", location=(60.0, 40.0)))
    assert midfield.score == 1 and midfield.quiet


def test_routine_passes_are_quiet_and_box_entries_are_not():
    stats = StatsEngine(HOME, AWAY)
    routine = ranked(stats, ev("Pass", **{"pass": PassDetails(end_location=(62.0, 45.0))}))
    box_pass = PassDetails(end_location=(108.0, 40.0))
    into_box = ranked(stats, ev("Pass", location=(90.0, 40.0), **{"pass": box_pass}))
    assert routine.score == 0 and routine.kind == "routine"
    assert into_box.score == 4 and into_box.reason == "ball into the box"


def test_goalkeeper_long_balls_are_routine():
    stats = StatsEngine(HOME, AWAY)
    long_ball = PassDetails(end_location=(100.0, 40.0))
    keeper = ranked(stats, ev("Pass", location=(10.0, 40.0), position="Goalkeeper", **{"pass": long_ball}))
    goal_kick = ranked(stats, ev("Pass", location=(6.0, 40.0), **{"pass": PassDetails(
        end_location=(70.0, 40.0), type="Goal Kick")}))
    assert keeper.score == 0 and goal_kick.score == 0


def test_half_markers_once_and_tension_boost_late_in_close_games():
    stats = StatsEngine(HOME, AWAY)
    assert ranked(stats, ev("Half End", team=HOME)).score == 6
    assert ranked(stats, ev("Half End", team=AWAY)).score == 0  # the feed's duplicate
    booking_early = ranked(stats, ev("Card", minute=20, card="Yellow Card"))
    booking_late = ranked(stats, ev("Card", minute=85, card="Yellow Card"))
    assert booking_late.score == booking_early.score + 1
    assert booking_late.reason == "booked, late in a close game"
    assert ranked(stats, ev("Half Start", minute=90, period=3)).reason == "kick-off"  # no boost on phases


def test_only_big_moments_beat_a_viewers_question():
    stats = StatsEngine(HOME, AWAY)
    beats = [
        goal(),
        ev("Card", card="Red Card"),
        ev("Foul Committed", foul=FoulDetails(penalty=True)),
        ev("Shot", location=(108.0, 40.0), shot=ShotDetails(outcome="Saved", type="Penalty")),
        ev("Shot", location=(114.0, 40.0), shot=ShotDetails(outcome="Saved")),  # big chance
        ev("Shot", location=(95.0, 40.0), shot=ShotDetails(outcome="Post")),
        ev("Foul Committed", location=(25.0, 40.0)),  # free kick about 22 m out
        ev("Shot", location=(95.0, 40.0), shot=ShotDetails(outcome="Off T", type="Free Kick")),
    ]
    waits = [
        ev("Card", card="Yellow Card"),
        ev("Foul Committed", location=(30.0, 40.0)),  # about 26 m: shooting range, but not 23 m
        ev("Foul Committed", location=(60.0, 40.0)),
        ev("Shot", location=(88.0, 40.0), shot=ShotDetails(outcome="Off T")),
        ev("Pass", **{"pass": PassDetails(end_location=(62.0, 45.0), type="Corner")}),
        ev("Half End", team=HOME),
    ]
    assert all(ranked(stats, e).beats_questions for e in beats)
    assert not any(ranked(stats, e).beats_questions for e in waits)
