"""Simulator invariants on a full match (ARCHITECTURE section 3, specs/simulator-*.md)."""

import math
from pathlib import Path

import pytest

from sim import config as C
from sim import rules as R
from sim.engine import ACT_INDEX, simulate
from sim.models import load_world
from sim.possession import goal_angle, xg

ROOT = Path(__file__).resolve().parent.parent
SEED = 11


@pytest.fixture(scope="module")
def world():
    return load_world(ROOT / "data" / "world.json")


@pytest.fixture(scope="module")
def result(world):
    return simulate(world, SEED)


def test_same_seed_identical_output(world, result):
    again = simulate(world, SEED)
    assert again.xy == result.xy and again.act == result.act
    strip = lambda evs: [{k: v for k, v in e.items() if k != "related"} for e in evs]  # noqa: E731
    assert strip(again.events) == strip(result.events)


def test_different_seed_differs(world, result):
    assert simulate(world, SEED + 1).xy != result.xy


def test_players_respect_speed_cap_and_pitch(world, result):
    paces = {p.id: p.attributes.pace for t in world.teams for p in t.players}
    for pid, xy in result.xy.items():
        xs, ys = xy[0::2], xy[1::2]
        assert len(xs) == C.DURATION_S + 1
        assert 0 <= min(xs) and max(xs) <= 1050 and 0 <= min(ys) and max(ys) <= 680, pid
        step = max(math.hypot(xs[i] - xs[i - 1], ys[i] - ys[i - 1]) for i in range(1, len(xs))) / 10
        if pid == "ball":
            assert step <= 30.0 + 0.15
        elif pid == "ref":
            assert step <= C.REF_SPEED + 0.15
        else:
            cap = min(9.0, 7.0 + 2.0 * paces[pid] / 99)
            assert step <= cap + 0.15, f"{pid} moved {step:.2f} m in a second"


def test_acceleration_limited_between_samples(result):
    # From rounded positions: a second difference of decimeter samples is off by at most 0.2 m per axis.
    for pid, xy in result.xy.items():
        if pid == "ball":
            continue
        xs, ys = xy[0::2], xy[1::2]
        for i in range(2, len(xs)):
            v1 = ((xs[i - 1] - xs[i - 2]) / 10, (ys[i - 1] - ys[i - 2]) / 10)
            v2 = ((xs[i] - xs[i - 1]) / 10, (ys[i] - ys[i - 1]) / 10)
            assert math.hypot(v2[0] - v1[0], v2[1] - v1[1]) <= 4.5 + 0.29, f"{pid} at {i}s"


def test_eleven_players_until_a_red_card(result):
    sent_off = ACT_INDEX["sent_off"]
    for side in ("azc", "rdm"):
        ids = [p for p in result.xy if p.startswith(side)]
        assert len(ids) == 11
        reds = sorted(t for pid, t in result.sent_off.items() if pid.startswith(side))
        for second in range(0, C.DURATION_S + 1, 30):
            on = sum(result.act[p][second] != sent_off for p in ids)
            assert on == 11 - sum(t <= second for t in reds)


def test_goals_equal_score(result):
    goals = [e for e in result.events if e["type"] == "goal"]
    assert [sum(g["team"] == t for g in goals) for t in ("azc", "rdm")] == result.score


def test_events_inside_match_and_time_ordered(result):
    times = [e["t"] for e in result.events]
    assert times == sorted(times)
    assert 0 <= times[0] and times[-1] <= C.DURATION_S


def test_event_types_are_known(result):
    from sim.models import RATED_EVENT_TYPES, RESTART_EVENT_TYPES
    assert {e["type"] for e in result.events} <= set(RATED_EVENT_TYPES + RESTART_EVENT_TYPES)


def test_xg_sanity_points_and_symmetry():
    # Sanity points from docs/research-attributes-and-sim.md, scaled by the calibrated intercept.
    close, far = xg(94.0, 34.0, 1, 0.0), xg(85.0, 34.0, 1, 0.0)
    assert 0.1 < close < 0.3 and far < 0.06 and close > 3 * far
    assert xg(11.0, 34.0, -1, 0.0) == pytest.approx(close)  # Redmond attacks the other way
    assert goal_angle(94.0, 30.0, 1) == pytest.approx(goal_angle(11.0, 38.0, -1))


def test_rules_offside_and_restarts():
    # Attacker beyond the second-last defender in the opponent half, ahead of the ball: offside.
    assert R.is_offside(90.0, 70.0, [104.0, 85.0, 80.0], 1)
    assert not R.is_offside(84.0, 70.0, [104.0, 85.0, 80.0], 1)
    assert not R.is_offside(40.0, 30.0, [104.0, 35.0], 1)  # own half
    assert R.out_of_play(50.0, 0.0, 1)[0:2] == ("throw_in", -1)
    assert R.out_of_play(105.0, 20.0, 1)[0] == "goal_kick"  # Azure kicked it over Redmond's line
    assert R.out_of_play(105.0, 20.0, -1)[0:2] == ("corner", 1)  # Redmond touched it last
    assert R.in_own_penalty_area(5.0, 34.0, 1) and not R.in_own_penalty_area(5.0, 34.0, -1)
