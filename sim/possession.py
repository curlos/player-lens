"""Decision and outcome formulas for the ball carrier (specs/simulator-possession.md).

Pure functions: geometry, xG, pass completion, option scoring helpers and the seeded softmax.
Coefficients live in sim/config.py and are calibration guesses.
"""

from __future__ import annotations

import math

import numpy as np

from sim import config as C


def z(attr: float) -> float:
    """Standardised skill term: 0 for an average pro (60), +1 per 10 points."""
    return (attr - 60.0) / 10.0


def logistic(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-x))


def dist(ax: float, ay: float, bx: float, by: float) -> float:
    return math.hypot(ax - bx, ay - by)


def segment_distance(px: float, py: float, ax: float, ay: float, bx: float, by: float) -> tuple[float, float]:
    """Distance from P to segment AB, and the projection parameter u (0 at A, 1 at B)."""
    dx, dy = bx - ax, by - ay
    L2 = dx * dx + dy * dy
    if L2 < 1e-9:
        return dist(px, py, ax, ay), 0.0
    u = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / L2))
    return dist(px, py, ax + u * dx, ay + u * dy), u


def goal_x(attack_dir: int) -> float:
    """x of the goal a team attacks."""
    return C.PITCH_L if attack_dir > 0 else 0.0


def goal_angle(x: float, y: float, attack_dir: int) -> float:
    """Angle (radians) the goal mouth subtends from (x, y)."""
    depth = abs(goal_x(attack_dir) - x)  # distance to the goal line; mirrored so both sides use the same branch
    a1 = math.atan2(C.PITCH_W / 2 - C.GOAL_HALF_WIDTH - y, depth)
    a2 = math.atan2(C.PITCH_W / 2 + C.GOAL_HALF_WIDTH - y, depth)
    return abs(a2 - a1)


def goal_distance(x: float, y: float, attack_dir: int) -> float:
    return dist(x, y, goal_x(attack_dir), C.PITCH_W / 2)


def xg(x: float, y: float, attack_dir: int, pressure: float, header: bool = False) -> float:
    """Chance quality: logit = a - 0.17 d + 1.0 angle, odds scaled down by pressure and for headers.

    Goalkeeper position and shooter skill are not part of xG (specs/rating-model.md).
    """
    d = goal_distance(x, y, attack_dir)
    logit = C.XG_INTERCEPT - C.XG_DIST * d + C.XG_ANGLE * goal_angle(x, y, attack_dir)
    odds = math.exp(logit) * math.exp(-C.XG_PRESSURE * pressure)
    if header:
        odds *= C.XG_HEADER
    return odds / (1.0 + odds)


def threat(x: float, y: float, attack_dir: int) -> float:
    """A smooth stand-in for an expected-threat grid: value of having the ball at (x, y)."""
    return 0.30 * math.exp(-goal_distance(x, y, attack_dir) / 14.0)


def pass_completion(d: float, passing: int, composure: int, pressure: float, final_third: bool,
                    lofted: bool, lane_gap: float, openness: float = 10.0, into_box: bool = False) -> float:
    """Research formula 1 plus two terms: lane_gap (how far inside 2.5 m of the lane the nearest defender is)
    and receiver marking (how far inside RECEIVER_MARKED_M the receiver's nearest defender is)."""
    logit = (C.PASS_BASE + C.PASS_Z * z(passing) - C.PASS_DIST * (d - 15.0)
             - C.PASS_PRESSURE * pressure * (1.0 - 0.1 * z(composure))
             - C.PASS_FINAL_THIRD * final_third - C.PASS_LOFTED * lofted - C.PASS_LANE * lane_gap
             - C.PASS_MARKED * max(0.0, C.RECEIVER_MARKED_M - openness) - C.PASS_INTO_BOX * into_box)
    return logistic(logit)


def pressure_on(px: float, py: float, opponents: list[tuple[float, float]]) -> float:
    """0-1: how closely the nearest opponent is on the player (1 = touching, 0 = 5 m or more)."""
    if not opponents:
        return 0.0
    nearest = min(dist(px, py, ox, oy) for ox, oy in opponents)
    return max(0.0, 1.0 - nearest / 5.0)


def softmax_choice(rng: np.random.Generator, scores: list[float], temperature: float) -> int:
    """Pick an index with probability proportional to exp(score / temperature), using the passed RNG."""
    m = max(scores)
    weights = [math.exp((s - m) / temperature) for s in scores]
    total = sum(weights)
    r = rng.random() * total
    acc = 0.0
    for i, w in enumerate(weights):
        acc += w
        if r <= acc:
            return i
    return len(scores) - 1


def decision_temperature(composure: int) -> float:
    return min(0.9, max(0.25, C.SOFTMAX_TEMP - C.SOFTMAX_TEMP_COMPOSURE * z(composure)))
