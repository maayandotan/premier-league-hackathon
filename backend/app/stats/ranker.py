"""Moment Ranker: how interesting is this event? Plain rules, no AI (issue #12).

It runs on every event, so it must be instant and predictable. The score (0-10)
tells the Producer whether to speak; the reason tells the agents what to talk about.
Call it AFTER the stats engine has seen the event.
"""
import math
from typing import Literal

from pydantic import BaseModel

from app.events.models import MatchEvent
from app.stats.engine import StatsEngine, pass_progression
from app.stats.geometry import METERS_PER_UNIT, distance_to_goal, in_box
from app.stats.xg import shot_xg

LATE_MINUTE = 80
# Events that stop play: the Analyst's chance to speak.
STOPPAGES = {"Foul Committed", "Offside", "Substitution", "Injury Stoppage", "Card", "Half End"}
BIG_CHANCE_XG = 0.3
# A viewer's answer waits only for these: a goal, a red card, a penalty, a real threat on goal
# (big chance or woodwork) and a free kick within this distance of goal.
DANGEROUS_FREE_KICK_METERS = 23.0

# Data terms -> plain words for the agents.
OUTCOME_WORDS = {
    "Goal": "scored", "Saved": "saved", "Saved To Post": "saved onto the post", "Off T": "off target",
    "Wayward": "off target", "Post": "hits the post", "Blocked": "blocked",
}

Kind = Literal["goal", "chance", "card", "set_piece", "attack", "stoppage", "phase", "routine"]


class Moment(BaseModel):
    score: int  # 0 routine ... 10 goal
    reason: str  # short, for the agents: "late equalizer", "big chance"
    kind: Kind
    quiet: bool  # play has stopped: a window for the Analyst
    beats_questions: bool = False  # important enough to be heard before a viewer's answer


def _goal(event: MatchEvent, stats: StatsEngine, momentum_before: float | None) -> Moment:
    team = event.team
    other = stats.away if team == stats.home else stats.home
    lead = stats.score[team] - stats.score[other]
    if lead == 0:
        reason = "equalizer"
    elif lead == 1:
        reason = "go-ahead goal"
    else:
        reason = "extends the lead" if lead > 1 else "pulls one back"
    if event.shot.type == "Penalty":
        reason = f"penalty {reason}"
    if event.minute >= LATE_MINUTE:
        reason = f"late {reason}"
    if momentum_before is not None:
        team_sign = 1 if team == stats.home else -1
        if momentum_before * team_sign <= -0.3:
            reason += ", against the run of play"
    return Moment(score=10, reason=reason, kind="goal", quiet=True)


def _shot(event: MatchEvent) -> Moment:
    outcome = OUTCOME_WORDS.get(event.shot.outcome, event.shot.outcome.lower())
    if event.period == 5:
        return Moment(score=8, reason=f"shootout penalty {outcome}", kind="chance", quiet=True)
    if event.shot.outcome == "Post":
        return Moment(score=7, reason="hits the post", kind="chance", quiet=False)
    xg = shot_xg(event) or 0
    if xg >= BIG_CHANCE_XG:
        return Moment(score=7, reason=f"big chance, {outcome}", kind="chance", quiet=False)
    if xg >= 0.1:
        return Moment(score=5, reason=f"half chance, {outcome}", kind="chance", quiet=False)
    return Moment(score=3, reason="speculative effort", kind="chance", quiet=False)


def _base(event: MatchEvent, stats: StatsEngine, momentum_before: float | None) -> Moment:
    if event.is_goal and event.period < 5:
        return _goal(event, stats, momentum_before)
    if event.shot is not None:
        return _shot(event)

    card = event.card or (event.foul.card if event.foul else None)
    if card in ("Red Card", "Second Yellow"):
        return Moment(score=9, reason="sent off", kind="card", quiet=True)
    if card == "Yellow Card":
        return Moment(score=5, reason="booked", kind="card", quiet=True)

    if event.type == "Foul Committed":
        if event.foul and event.foul.penalty:
            return Moment(score=9, reason="penalty awarded", kind="set_piece", quiet=True)
        # Coordinates are from the fouling team's view: near x = 0 is their own goal.
        if event.location and event.location[0] <= 35:
            return Moment(score=5, reason="free kick in shooting range", kind="set_piece", quiet=True)
        return Moment(score=1, reason="foul", kind="stoppage", quiet=True)

    if event.type == "Offside":
        return Moment(score=3, reason="offside", kind="stoppage", quiet=True)
    if event.type in ("Half Start", "Half End"):
        # The feed has one per team; only the home team's copy is worth a line.
        score = 6 if event.team == stats.home else 0
        if event.type == "Half Start":
            return Moment(score=score, reason="kick-off", kind="phase", quiet=False)
        # Say which whistle it is: "end of the half" at the end of the match made the Caller say
        # "half time whistle blows" at full time.
        end = {1: "half-time", 2: "full time", 3: "end of the first half of extra time",
               4: "end of extra time"}.get(event.period, "end of the half")
        return Moment(score=score, reason=end, kind="phase", quiet=True)
    if event.type in ("Substitution", "Injury Stoppage"):
        return Moment(score=2, reason=event.type.lower(), kind="stoppage", quiet=True)

    if event.pass_ is not None:
        if event.pass_.goal_assist or event.pass_.shot_assist:
            return Moment(score=5, reason="sets up a shot", kind="attack", quiet=False)
        if event.pass_.type == "Corner":
            return Moment(score=4, reason="corner", kind="set_piece", quiet=False)
        # A keeper's long ball travels far but is rarely a moment worth calling.
        if event.pass_.type == "Goal Kick" or event.position == "Goalkeeper":
            return Moment(score=0, reason="goalkeeper distribution", kind="routine", quiet=False)
        prog = pass_progression(event)
        if prog and prog["into_box"]:
            return Moment(score=4, reason="ball into the box", kind="attack", quiet=False)
        rarity = stats.pass_rarity(event)
        if rarity and rarity["progressive"] and rarity["share_of_passes_this_good"] <= 0.05:
            return Moment(score=4, reason="rare line-breaking pass", kind="attack", quiet=False)
        return Moment(score=0, reason="pass", kind="routine", quiet=False)

    if event.type == "Carry" and event.carry and event.carry.end_location and event.location:
        if in_box(*event.carry.end_location[:2]) and not in_box(*event.location[:2]):
            return Moment(score=4, reason="carries into the box", kind="attack", quiet=False)
    if event.type == "Dribble" and event.outcome == "Complete" and event.location and event.location[0] >= 80:
        return Moment(score=3, reason="beats a defender in the final third", kind="attack", quiet=False)

    return Moment(score=0, reason=event.type.lower(), kind="routine", quiet=event.type in STOPPAGES)


def _within_meters_of_goal(distance_units: float, meters: float) -> bool:
    return distance_units * METERS_PER_UNIT <= meters


def beats_questions(event: MatchEvent, moment: Moment) -> bool:
    """Does this moment outrank a viewer's question? Everything else waits for the answer."""
    if moment.kind == "goal":
        return True
    if event.shot is not None:
        if event.period == 5 or event.shot.type == "Penalty":
            return True
        if event.shot.type == "Free Kick" and event.location:
            x, y = event.location[:2]
            if _within_meters_of_goal(distance_to_goal(x, y), DANGEROUS_FREE_KICK_METERS):
                return True
        # A real threat on goal: a big chance or the woodwork.
        return event.shot.outcome == "Post" or (shot_xg(event) or 0) >= BIG_CHANCE_XG
    card = event.card or (event.foul.card if event.foul else None)
    if card in ("Red Card", "Second Yellow"):
        return True
    if event.type == "Foul Committed":
        if event.foul and event.foul.penalty:
            return True
        if event.location:
            # The fouling team's view: their own goal is at (0, 40), where the free kick is aimed.
            x, y = event.location[:2]
            return _within_meters_of_goal(math.hypot(x, y - 40), DANGEROUS_FREE_KICK_METERS)
    return False


def rank(event: MatchEvent, stats: StatsEngine, momentum_before: float | None = None) -> Moment:
    """Score an event 0-10. momentum_before (the stats engine's momentum value just
    before this event) lets a goal be called 'against the run of play'."""
    moment = _base(event, stats, momentum_before)
    # Tension: in a close game late on, every notable moment matters a bit more.
    close = abs(stats.score[stats.home] - stats.score[stats.away]) <= 1
    late_and_close = event.minute >= LATE_MINUTE and close and event.period < 5
    if late_and_close and 2 <= moment.score < 9 and moment.kind != "phase":
        reason = f"{moment.reason}, late in a close game"
        moment = moment.model_copy(update={"score": moment.score + 1, "reason": reason})
    return moment.model_copy(update={"beats_questions": beats_questions(event, moment)})
