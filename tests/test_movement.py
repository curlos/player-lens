"""move_player() invariants (specs/simulator-movement.md): speed cap, acceleration limit, arrival, bounds."""

import math
import re
from pathlib import Path

import numpy as np
import pytest

from sim import config as C
from sim.movement import Body, move_player, place_body, player_accel, player_speed

ROOT = Path(__file__).resolve().parent.parent


def body(pace: int = 90, fatigue: float = 0.0) -> Body:
    b = Body("azc_09", player_speed(pace), player_accel(pace))
    b.fatigue = fatigue
    return b


def test_derived_speed_and_accel_from_pace():
    assert player_speed(99) == pytest.approx(9.0)
    assert player_speed(50) == pytest.approx(7.0 + 2.0 * 50 / 99)
    assert player_accel(99) == pytest.approx(4.5)


@pytest.mark.parametrize("fatigue", [0.0, 0.5, 1.0])
def test_random_targets_respect_speed_and_accel_limits(fatigue):
    rng = np.random.default_rng(1)
    b = body(fatigue=fatigue)
    place_body(b, 50, 30)
    tx, ty = 60.0, 30.0
    for _ in range(3000):
        if rng.random() < 0.2:  # targets jump around, as in a press or a turnover
            tx, ty = rng.uniform(0, C.PITCH_L), rng.uniform(0, C.PITCH_W)
        vx, vy, x, y = b.vx, b.vy, b.x, b.y
        move_player(b, tx, ty, 9.0)
        moved = math.hypot(b.x - x, b.y - y)
        assert moved <= b.max_speed() + 1e-9 <= 9.0 + 1e-9
        assert math.hypot(b.vx - vx, b.vy - vy) <= b.accel() + 1e-9
        assert 0 <= b.x <= C.PITCH_L and 0 <= b.y <= C.PITCH_W


def test_reaches_and_stops_on_target_without_jitter():
    b = body()
    place_body(b, 10, 10)
    for _ in range(30):
        move_player(b, 40, 10, 9.0)
    assert (b.x, b.y) == (40, 10)
    move_player(b, 40, 10, 9.0)
    assert (b.x, b.y) == (40, 10) and b.speed == 0.0


def test_35m_run_takes_about_four_seconds():
    b = body(pace=88)
    place_body(b, 10, 34)
    ticks = 0
    while b.x < 44.5 and ticks < 20:
        move_player(b, 60, 34, 9.0)  # run through the point, as a sprint would
        ticks += 1
    assert 4 <= ticks <= 7


def test_reversal_takes_several_ticks():
    b = body()
    place_body(b, 50, 34)
    for _ in range(6):
        move_player(b, 100, 34, 9.0)
    assert b.vx > 5
    move_player(b, 0, 34, 9.0)
    assert b.vx > 0  # still moving forward: it brakes first, never flips in one tick


def test_only_movement_module_writes_positions():
    """Positions and velocities are written only in sim/movement.py."""
    pattern = re.compile(r"\.(x|y|vx|vy)\s*(\+|-|\*|/)?=(?!=)")
    offenders = []
    for path in sorted((ROOT / "sim").glob("*.py")):
        if path.name == "movement.py":
            continue
        for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if pattern.search(line):
                offenders.append(f"{path.name}:{n}: {line.strip()}")
    assert offenders == []
