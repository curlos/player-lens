"""Laws-of-the-game helpers (specs/match-rules.md): areas, offside, out of play, set-piece takers.

Pure functions over plain numbers so they are easy to test. The engine applies them.
"""

from __future__ import annotations

from typing import Iterable, Protocol

from sim import config as C


class HasAttrs(Protocol):
    id: str
    on_pitch: bool
    attrs: dict[str, int]


def own_goal_x(attack_dir: int) -> float:
    return 0.0 if attack_dir > 0 else C.PITCH_L


def in_own_penalty_area(x: float, y: float, attack_dir: int) -> bool:
    """True if (x, y) is inside the penalty area of the team attacking in attack_dir (their own box)."""
    depth = x if attack_dir > 0 else C.PITCH_L - x
    return depth <= C.BOX_DEPTH and abs(y - C.PITCH_W / 2) <= C.BOX_HALF_WIDTH


def in_attacking_box(x: float, y: float, attack_dir: int) -> bool:
    """True if (x, y) is inside the box this team attacks."""
    return in_own_penalty_area(x, y, -attack_dir)


def advance(x: float, attack_dir: int) -> float:
    """Distance from the team's own goal line along its attacking direction."""
    return x if attack_dir > 0 else C.PITCH_L - x


def second_last_defender_x(defender_xs: Iterable[float], attack_dir: int) -> float:
    """x of the second-last defender, seen by a team attacking in attack_dir (defenders' goal line is ahead)."""
    xs = sorted(defender_xs, reverse=attack_dir > 0)  # closest to their goal line first
    return xs[1] if len(xs) >= 2 else (C.PITCH_L if attack_dir > 0 else 0.0)


def is_offside(receiver_x: float, ball_x: float, defender_xs: Iterable[float], attack_dir: int) -> bool:
    """Basic offside at the moment of a pass: in the opponent half, ahead of the ball and the second-last defender."""
    half = C.PITCH_L / 2
    line = second_last_defender_x(defender_xs, attack_dir)
    ahead = (lambda a, b: a > b) if attack_dir > 0 else (lambda a, b: a < b)
    return ahead(receiver_x, half) and ahead(receiver_x, ball_x) and ahead(receiver_x, line)


def out_of_play(x: float, y: float, last_touch_dir: int) -> tuple[str, int, tuple[float, float]]:
    """Restart for a ball leaving at (x, y). Returns (restart type, attack_dir of the team awarded it, spot).

    Touchline: throw-in to the other team. Goal line: goal kick if the attackers touched it last, else corner.
    """
    if y <= 0.0 or y >= C.PITCH_W:
        spot = (min(C.PITCH_L - 1.0, max(1.0, x)), 0.0 if y <= 0.0 else C.PITCH_W)
        return "throw_in", -last_touch_dir, spot
    # Goal line: the team defending this line attacks away from it.
    defending_dir = 1 if x <= 0.0 else -1
    if last_touch_dir != defending_dir:  # attackers touched it last
        gx = C.GOAL_AREA_DEPTH if defending_dir > 0 else C.PITCH_L - C.GOAL_AREA_DEPTH
        return "goal_kick", defending_dir, (gx, C.PITCH_W / 2)
    cx = 0.0 if x <= 0.0 else C.PITCH_L
    cy = 0.0 if y < C.PITCH_W / 2 else C.PITCH_W
    return "corner", -defending_dir, (cx, cy)


def set_piece_order(players: Iterable[HasAttrs]) -> list[HasAttrs]:
    """On-pitch outfield players ranked as set-piece takers: Set pieces, then Finishing, then Composure."""
    ranked = [p for p in players if p.on_pitch and not getattr(p, "is_gk", False)]
    return sorted(ranked, key=lambda p: (-p.attrs["set_pieces"], -p.attrs["finishing"], -p.attrs["composure"], p.id))


def set_piece_taker(players: Iterable[HasAttrs], exclude: str | None = None) -> HasAttrs:
    """Designated penalty and free-kick taker; the fouled player (exclude) does not take it."""
    return next(p for p in set_piece_order(players) if p.id != exclude)
