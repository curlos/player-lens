"""Movement primitives (specs/simulator-movement.md).

This is the only module that writes positions or velocities. Players and the referee move only
through ``move_player()``; ``place_body()`` is used once, for the kickoff layout at second 0. The ball
moves through ``place_ball()`` / ``move_ball_toward()`` (it is not a player and has its own cap).
``tests/test_simulator.py`` scans the source to keep it that way.
"""

from __future__ import annotations

import math

from sim import config as C


class Body:
    """Anything that walks: a player or the referee."""

    __slots__ = ("id", "x", "y", "vx", "vy", "base_speed", "base_accel", "fatigue")

    def __init__(self, body_id: str, base_speed: float, base_accel: float):
        self.id = body_id
        self.x = self.y = 0.0
        self.vx = self.vy = 0.0
        self.base_speed = min(C.SPEED_CAP, base_speed)
        self.base_accel = base_accel
        self.fatigue = 0.0

    @property
    def speed(self) -> float:
        return math.hypot(self.vx, self.vy)

    def max_speed(self) -> float:
        """Top speed after fatigue, m/s."""
        return self.base_speed * (1.0 - C.FATIGUE_SPEED_LOSS * self.fatigue)

    def accel(self) -> float:
        """Acceleration after fatigue, m/s^2 (same fatigue factor as top speed)."""
        return self.base_accel * (1.0 - C.FATIGUE_SPEED_LOSS * self.fatigue)


def player_speed(pace: int) -> float:
    return min(C.SPEED_CAP, C.BASE_SPEED + C.PACE_SPEED * pace / 99.0)


def player_accel(pace: int) -> float:
    return C.BASE_ACCEL + C.PACE_ACCEL * pace / 99.0


def clamp_to_pitch(x: float, y: float, margin: float = 0.0) -> tuple[float, float]:
    return (min(C.PITCH_L - margin, max(margin, x)), min(C.PITCH_W - margin, max(margin, y)))


def place_body(body: Body, x: float, y: float) -> None:
    """Initial placement (kickoff layout at second 0 only). Never used during play."""
    body.x, body.y = clamp_to_pitch(x, y)
    body.vx = body.vy = 0.0


def _stopping_cap(d: float, a: float) -> float:
    """Largest speed v (dt = 1) with v + stop(v - a) <= d, where stop(u) sums the per-tick braking steps
    u + (u - a) + (u - 2a) + ... while positive (the exact discrete form of u (u + a) / (2 a)).

    If v lies in (m a, (m + 1) a] the player covers (m + 1) v - a m (m + 1) / 2 before stopping, so the
    cap is the first m whose solution falls inside its interval.
    """
    if a <= 0 or d <= 0:
        return max(0.0, d)
    m = 0
    while True:
        v = (d + a * m * (m + 1) / 2.0) / (m + 1)
        if v <= (m + 1) * a or m > 50:
            return v
        m += 1


def _enforce_walls(x: float, y: float, vx: float, vy: float, nvx: float, nvy: float, a: float) -> tuple[float, float]:
    """Keep each velocity component heading at a line within the stopping cap for the distance left.

    Holding this every tick guarantees (by induction on the stopping rule) that a player can always stop
    before the line, so the final clamp never has to stop anyone harder than the acceleration limit.
    The constrained axis moves by at most ``a``; the other axis gives up budget so |dv| <= a still holds.
    """
    out = [nvx, nvy]
    old = (vx, vy)
    room = ((C.PITCH_L - x, x), (C.PITCH_W - y, y))  # (ahead, behind) per axis
    constrained = [False, False]
    for i in (0, 1):
        ahead, behind = room[i]
        if out[i] > 0 and out[i] > _stopping_cap(ahead, a):
            out[i], constrained[i] = max(_stopping_cap(ahead, a), old[i] - a), True
        elif out[i] < 0 and -out[i] > _stopping_cap(behind, a):
            out[i], constrained[i] = -max(_stopping_cap(behind, a), -old[i] - a), True
    d = [out[0] - old[0], out[1] - old[1]]
    if math.hypot(*d) > a and constrained != [True, True]:
        free = 0 if not constrained[0] else 1
        budget = math.sqrt(max(0.0, a * a - d[1 - free] ** 2))
        d[free] = math.copysign(min(abs(d[free]), budget), d[free])
        out[free] = old[free] + d[free]
    return out[0], out[1]


def _wall_safe(x: float, y: float, wx: float, wy: float, a: float) -> tuple[float, float]:
    """Cap each velocity component heading at a touchline or goal line so the player can still stop inside."""
    if wx > 0:
        wx = min(wx, _stopping_cap(C.PITCH_L - x, a))
    elif wx < 0:
        wx = -min(-wx, _stopping_cap(x, a))
    if wy > 0:
        wy = min(wy, _stopping_cap(C.PITCH_W - y, a))
    elif wy < 0:
        wy = -min(-wy, _stopping_cap(y, a))
    return wx, wy


def move_player(body: Body, tx: float, ty: float, speed_cap: float) -> float:
    """Move one body one tick (dt = 1 s) toward (tx, ty). The only position update in the simulator.

    Limits, in order: desired speed <= min(speed_cap, max_speed, braking sqrt(2 a d), d); applied speed
    also respects the discrete stopping rule; the velocity change is a vector limited to accel x dt;
    the result is clamped to the pitch. Returns the speed actually moved (m/s).
    """
    tx, ty = clamp_to_pitch(tx, ty)
    acc = body.accel()
    a = acc  # accel x dt with dt = 1
    dx, dy = tx - body.x, ty - body.y
    d = math.hypot(dx, dy)
    v = body.speed
    if d <= C.ARRIVAL_RADIUS and math.hypot(dx - body.vx, dy - body.vy) <= a:
        # Arrival: step onto the target and stop there (velocity is the step itself, so it is 0 next tick).
        body.vx, body.vy = dx, dy
        body.x, body.y = tx, ty
        return d
    if d < 1e-9:
        ux, uy, desired, cap = 0.0, 0.0, 0.0, 0.0
    else:
        ux, uy = dx / d, dy / d
        desired = min(max(0.0, speed_cap), body.max_speed(), math.sqrt(2.0 * acc * d), d)
        cap = _stopping_cap(d, a)
    s = max(min(desired, cap), v - a)
    wx, wy = ux * s, uy * s
    if v > 1e-9 and (body.vx * ux + body.vy * uy) < 0:
        # Target is behind: brake along the current heading first, then turn back (no snapping).
        keep = max(0.0, v - a) / v
        wx, wy = body.vx * keep, body.vy * keep
    wx, wy = _wall_safe(body.x, body.y, wx, wy, a)
    ddx, ddy = wx - body.vx, wy - body.vy
    dv = math.hypot(ddx, ddy)
    if dv > a:
        ddx, ddy = ddx * a / dv, ddy * a / dv
    nvx, nvy = body.vx + ddx, body.vy + ddy
    nvx, nvy = _enforce_walls(body.x, body.y, body.vx, body.vy, nvx, nvy, a)
    sp = math.hypot(nvx, nvy)
    if sp > C.SPEED_CAP:  # hard cap; unreachable in practice because max_speed <= 9
        nvx, nvy = nvx * C.SPEED_CAP / sp, nvy * C.SPEED_CAP / sp
    ox, oy = body.x, body.y
    body.x, body.y = clamp_to_pitch(ox + nvx, oy + nvy)
    body.vx, body.vy = body.x - ox, body.y - oy
    return math.hypot(body.vx, body.vy)


def update_fatigue(body: Body, speed: float, work_rate: int, stamina: int) -> None:
    """fatigue += k (speed / max_speed)^2 load; load rises with Work rate, build rate falls with Stamina."""
    if speed < C.ACT_WALK:
        body.fatigue = max(0.0, body.fatigue - C.FATIGUE_RECOVERY)
        return
    load = (0.6 + 0.8 * work_rate / 99.0) * (1.6 - stamina / 99.0)
    ratio = speed / max(1e-6, body.max_speed())
    body.fatigue = min(C.FATIGUE_MAX, body.fatigue + C.FATIGUE_K * ratio * ratio * load)


def speed_label(speed: float) -> str:
    if speed < C.ACT_STAND:
        return "stand"
    if speed < C.ACT_WALK:
        return "walk"
    if speed < C.ACT_JOG:
        return "jog"
    if speed < C.ACT_RUN:
        return "run"
    return "sprint"


class Ball:
    """The ball's position. State (carried, in flight, loose, dead) lives in the engine."""

    __slots__ = ("x", "y")

    def __init__(self) -> None:
        self.x, self.y = C.PITCH_L / 2, C.PITCH_W / 2


def place_ball(ball: Ball, x: float, y: float) -> None:
    """Put the ball on a point (carried ahead of a player, or a flight sample). Kept on the pitch."""
    ball.x, ball.y = clamp_to_pitch(x, y)


def move_ball_toward(ball: Ball, x: float, y: float, max_step: float) -> None:
    """Move the ball at most max_step meters toward (x, y): fetching it to a restart spot, or a loose roll."""
    dx, dy = x - ball.x, y - ball.y
    d = math.hypot(dx, dy)
    if d <= max_step:
        place_ball(ball, x, y)
    else:
        place_ball(ball, ball.x + dx * max_step / d, ball.y + dy * max_step / d)
