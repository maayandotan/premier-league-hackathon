"""The synthetic match generator (#9): valid, realistic, reproducible, and the script is kept."""
import statistics
from collections import Counter

import pytest

from app.stats.engine import StatsEngine
from app.stats.ranker import rank
from app.synthetic.scenarios import SCENARIOS
from app.synthetic.simulator import generate_match

OPEN_MATCHES = [generate_match(SCENARIOS["open"], seed) for seed in range(20)]


def replay_stats(match):
    stats = StatsEngine(match.info.home.name, match.info.away.name)
    moments = []
    for event in match.events:
        before = stats.momentum()["value"]
        stats.update(event)
        moments.append(rank(event, stats, before))
    return stats, moments


def test_same_seed_same_match():
    first = generate_match(SCENARIOS["comeback"], 3).model_dump_json()
    assert first == generate_match(SCENARIOS["comeback"], 3).model_dump_json()
    assert first != generate_match(SCENARIOS["comeback"], 4).model_dump_json()


@pytest.mark.parametrize("match", OPEN_MATCHES[:5] + [generate_match(SCENARIOS["red_card"], 1)])
def test_every_event_is_well_formed(match):
    teams = {match.info.home.name, match.info.away.name}
    squad = {p.name for team in (match.info.home, match.info.away) for p in team.players}
    assert [e.index for e in match.events] == list(range(1, len(match.events) + 1))
    for previous, event in zip(match.events, match.events[1:], strict=False):
        if event.period == previous.period:
            assert event.match_seconds >= previous.match_seconds
    assert min(e.match_seconds for e in match.events if e.period == 2) == 45 * 60
    for event in match.events:
        assert event.team in teams
        assert event.player is None or event.player in squad
        if event.location:
            assert 0 <= event.location[0] <= 120 and 0 <= event.location[1] <= 80
        if event.type == "Pass":
            assert event.pass_.end_location is not None and event.player
        assert event.type in ("Half Start", "Half End", "Substitution") or event.location


def test_players_who_leave_never_play_again():
    for match in OPEN_MATCHES + [generate_match(SCENARIOS["red_card"], 2)]:
        gone: set[str] = set()
        for event in match.events:
            assert event.player not in gone, f"{event.player} played after leaving ({match.info.id})"
            if event.substitution:
                gone.add(event.player)
            if event.foul and event.foul.card in ("Red Card", "Second Yellow"):
                gone.add(event.player)


def test_substitutes_are_not_taken_off_again():
    for match in OPEN_MATCHES:
        came_on = {e.substitution.replacement for e in match.events if e.substitution}
        assert not came_on & {e.player for e in match.events if e.substitution}


def test_averages_look_like_football():
    """General football knowledge, not real data (DATA_POLICY.md rule 5)."""
    def mean(count):
        return statistics.mean(count(m) for m in OPEN_MATCHES)

    def of_type(type_):
        return lambda m: sum(e.type == type_ for e in m.events)

    assert 1000 <= mean(lambda m: len(m.events)) <= 1350
    assert 19 <= mean(of_type("Shot")) <= 31
    assert 1.8 <= mean(lambda m: sum(e.is_goal for e in m.events)) <= 3.6
    assert 16 <= mean(of_type("Foul Committed")) <= 28
    assert 7 <= mean(lambda m: sum(bool(e.pass_ and e.pass_.type == "Corner") for e in m.events)) <= 14
    yellows = mean(lambda m: sum(bool(e.foul and e.foul.card == "Yellow Card") for e in m.events))
    assert 2 <= yellows <= 5
    for match in OPEN_MATCHES:
        stats, _ = replay_stats(match)
        assert 38 <= stats.possession()[match.info.home.name] <= 62


@pytest.mark.parametrize("name", ["comeback", "red_card", "late_equaliser"])
def test_the_script_is_kept(name):
    scenario = SCENARIOS[name]
    match = generate_match(scenario, 11)
    goals = [e for e in match.events if e.is_goal]
    scripted = [b for b in scenario.beats if b.kind == "goal"]
    assert [(g.team, g.player) for g in goals] == [(b.team, b.player) for b in scripted]
    for goal, beat in zip(goals, scripted, strict=True):
        assert beat.minute <= goal.minute <= beat.minute + 2
    reds = [e for e in match.events if e.foul and e.foul.card in ("Red Card", "Second Yellow")]
    sent_off = [(b.team, b.player) for b in scenario.beats if b.kind == "red_card"]
    assert [(e.team, e.player) for e in reds] == sent_off


def test_scripted_misses_are_big_chances():
    match = generate_match(SCENARIOS["comeback"], 5)
    _, moments = replay_stats(match)
    misses = [(e, m) for e, m in zip(match.events, moments, strict=True)
              if e.shot and e.player == "M. Ferro" and 39 <= e.minute <= 41]
    assert misses and misses[0][1].score >= 7


def test_goals_are_set_up_like_real_goals():
    match = generate_match(SCENARIOS["comeback"], 2)
    by_pattern = Counter(e.play_pattern for e in match.events if e.is_goal)
    assert by_pattern == {"From Counter": 1, "From Corner": 1, "Regular Play": 1}
    assists = [e for e in match.events if e.pass_ and e.pass_.goal_assist]
    assert len(assists) == 3  # every scripted goal comes from a pass


def test_commentary_has_enough_to_say_but_not_everything():
    _, moments = replay_stats(generate_match(SCENARIOS["comeback"], 1))
    worth_a_line = sum(m.score >= 3 for m in moments)
    assert 70 <= worth_a_line <= 250
