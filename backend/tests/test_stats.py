from app.events.models import MatchEvent, PassDetails, ShotDetails
from app.stats.engine import StatsEngine, pass_progression
from app.stats.xg import PENALTY_XG, shot_xg

HOME, AWAY = "Northbridge FC", "Westvale United"


def shot(x, y, index=1, team=HOME, minute=10, period=1, outcome="Saved", **shot_fields):
    return MatchEvent(id=f"s{index}", index=index, period=period, minute=minute, second=0, type="Shot",
                      team=team, location=(x, y), shot=ShotDetails(outcome=outcome, **shot_fields))


def a_pass(start, end, index=1, team=HOME, minute=10, outcome="Complete"):
    return MatchEvent(id=f"p{index}", index=index, period=1, minute=minute, second=0, type="Pass", team=team,
                      location=start, **{"pass": PassDetails(end_location=end, outcome=outcome)})


def test_xg_rewards_closer_and_more_central_shots():
    six_yard = shot_xg(shot(114, 40))
    edge_of_box = shot_xg(shot(102, 40))
    long_range = shot_xg(shot(90, 40))
    tight_angle = shot_xg(shot(114, 10))
    assert six_yard > edge_of_box > long_range
    assert six_yard > tight_angle
    assert 0 < long_range < 0.1 and 0.3 < six_yard < 0.8


def test_xg_penalty_and_header():
    assert shot_xg(shot(108, 40, type="Penalty")) == PENALTY_XG
    assert shot_xg(shot(110, 40, body_part="Head")) < shot_xg(shot(110, 40))


def test_pass_progression():
    progressive = pass_progression(a_pass((50, 40), (90, 40)))
    sideways = pass_progression(a_pass((50, 10), (50, 70)))
    assert progressive["progressive"] and progressive["gain"] > 30
    assert not sideways["progressive"]
    assert pass_progression(a_pass((95, 40), (105, 40)))["into_box"]


def test_score_counts_goals_but_not_shootout():
    stats = StatsEngine(HOME, AWAY)
    stats.update(shot(110, 40, index=1, outcome="Goal"))
    stats.update(shot(108, 40, index=2, team=AWAY, period=5, minute=120, outcome="Goal", type="Penalty"))
    assert stats.score == {HOME: 1, AWAY: 0}
    assert stats.shootout == {HOME: 0, AWAY: 1}
    assert stats.shots == {HOME: 1, AWAY: 0}


def test_possession_and_momentum_follow_who_attacks():
    stats = StatsEngine(HOME, AWAY)
    for i in range(6):
        stats.update(a_pass((85, 40), (105, 40), index=i, minute=20))
    stats.update(a_pass((30, 40), (40, 40), index=10, team=AWAY, minute=20))
    stats.update(shot(110, 40, index=11, minute=21))
    assert stats.possession()[HOME] > 80
    momentum = stats.momentum()
    assert momentum["value"] > 0.5 and momentum["leader"] == HOME


def test_recent_window_forgets_old_events():
    stats = StatsEngine(HOME, AWAY)
    for i in range(5):
        stats.update(a_pass((50, 40), (60, 40), index=i, team=AWAY, minute=5))
    stats.update(a_pass((50, 40), (60, 40), index=10, minute=30))
    assert stats.possession(recent=True) == {HOME: 100.0, AWAY: 0.0}
    assert stats.possession()[AWAY] > stats.possession()[HOME]


def test_pass_rarity_compares_with_this_match():
    stats = StatsEngine(HOME, AWAY)
    for i in range(9):
        stats.update(a_pass((50, 40), (52, 40), index=i))
    big = a_pass((40, 40), (100, 40), index=20)
    stats.update(big)
    assert stats.pass_rarity(big)["share_of_passes_this_good"] == 0.1
