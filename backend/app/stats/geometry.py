"""Pitch geometry on the 120 x 80 pitch, attacking towards x = 120."""
import math

GOAL_X = 120.0
GOAL_Y = 40.0
POST_HALF_WIDTH = 4.0  # goal is 8 units wide (y 36-44)
METERS_PER_UNIT = 105 / 120  # a 105 m pitch drawn 120 units long


def distance_to_goal(x: float, y: float) -> float:
    return math.hypot(GOAL_X - x, GOAL_Y - y)


def goal_angle(x: float, y: float) -> float:
    """Angle (radians) the goal mouth covers from (x, y): wider means an easier target."""
    dx = max(GOAL_X - x, 1e-6)
    left = math.atan2(GOAL_Y + POST_HALF_WIDTH - y, dx)
    right = math.atan2(GOAL_Y - POST_HALF_WIDTH - y, dx)
    return abs(left - right)


def in_box(x: float, y: float) -> bool:
    return x >= 102 and 18 <= y <= 62


def in_final_third(x: float) -> bool:
    return x >= 80
