"""Baseline expected goals (xG) from shot distance and angle.

A hand-set logistic formula: no data was used to fit it. The trained model with SHAP
explanations comes in issue #11; this is the fallback and the starting point.
"""
import math

from app.events.models import MatchEvent
from app.stats.geometry import METERS_PER_UNIT, distance_to_goal, goal_angle

PENALTY_XG = 0.76


def shot_xg(event: MatchEvent) -> float | None:
    """Chance a shot like this becomes a goal, 0-1. None if the event isn't a shot with a location."""
    if event.shot is None or event.location is None:
        return None
    if event.shot.type == "Penalty":
        return PENALTY_XG
    x, y = event.location[:2]
    distance_m = distance_to_goal(x, y) * METERS_PER_UNIT
    angle = goal_angle(x, y)
    # Closer and wider-angle shots score more; headers and pressure lower the odds.
    logit = -1.1 - 0.11 * distance_m + 1.6 * angle
    if event.shot.body_part == "Head":
        logit -= 0.9
    if event.under_pressure:
        logit -= 0.3
    return round(1 / (1 + math.exp(-logit)), 3)
