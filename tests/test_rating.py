"""Rating engine tests: soft cap, repeat decay, caps, the rating sum, and the off-ball definitions."""

from pathlib import Path

import pytest

from rating import config as RC
from rating import offball
from rating.engine import _soft_cap, credits, rate
from sim.models import load_world
from sim.pipeline import MatchInfo, build_match

ROOT = Path(__file__).resolve().parent.parent


def ev(i, t, etype, player, other=None, **kw):
    base = {"id": f"e_{i:04d}", "t": float(t), "type": etype, "team": player[:3], "player": player, "other": other,
            "from": (50.0, 34.0), "to": None, "outcome": kw.pop("outcome", "success"), "xg": kw.pop("xg", None),
            "speed_kmh": None, "related": []}
    base.update(kw)
    return base


def test_soft_cap_examples_from_spec():
    # At 9.5 a goal adds +0.17; at 8.5 it adds +0.5 (specs/rating-model.md).
    assert round(1.0 * _soft_cap(9.5, 1.0), 2) == 0.17
    assert round(1.0 * _soft_cap(8.5, 1.0), 2) == 0.5
    assert _soft_cap(6.0, 1.0) == 1.0 and _soft_cap(6.0, -1.0) == 1.0
    assert _soft_cap(4.0, -1.5) == pytest.approx(1.0 / 3.0)  # losses shrink near the bottom
    assert _soft_cap(3.15, -1.5) == pytest.approx((3.15 - 3.1) / 1.5)  # and never go below 3.1


def test_rating_never_leaves_display_range():
    goals = [ev(i, i * 10, "goal", "azc_09", xg=0.3) for i in range(1, 30)]
    reds = [ev(100 + i, 400 + i, "card_red", "rdm_04") for i in range(10)]
    entries = rate(goals + reds)
    star = [e for e in entries if e["player"] == "azc_09"]
    assert star[-1]["rating_after"] <= RC.MAX_RATING
    assert star[3]["rating_after"] < 9.9  # soft cap: the climb slows down
    assert min(e["rating_after"] for e in entries if e["player"] == "rdm_04") >= RC.MIN_RATING


def test_entry_arithmetic_and_running_sum():
    events = [ev(1, 10, "tackle", "azc_06", "rdm_10"), ev(2, 20, "tackle", "azc_06", "rdm_09"),
              ev(3, 30, "foul", "azc_06", "rdm_08"), ev(4, 40, "goal", "rdm_09", "rdm_10", xg=0.4)]
    entries = rate(events)
    running = {}
    for e in entries:
        assert abs(e["delta"] - e["raw_delta"] * e["scale"]) <= 0.01
        running[e["player"]] = running.get(e["player"], 6.0) + e["delta"]
        assert abs(running[e["player"]] - e["rating_after"]) <= 0.01
    tackles = [e for e in entries if e["reason_code"] == "tackle"]
    assert tackles[1]["raw_delta"] < tackles[0]["raw_delta"]  # repeat decay
    codes = {(e["player"], e["reason_code"]) for e in entries}
    assert ("rdm_10", "dispossessed") in codes and ("rdm_10", "assist") in codes
    assert ("azc_01", "gk_goal_conceded") in codes and ("rdm_08", "foul_won") in codes


def test_goalkeeper_values():
    save = credits(ev(1, 10, "save", "rdm_01", "azc_09", xg=0.8))
    assert save[0][2] == pytest.approx(0.6)  # 0.1 + 0.8 * 0.8 = 0.74, capped at 0.6
    conceded = [c for c in credits(ev(2, 20, "goal", "azc_09", xg=0.05)) if c[1] == "gk_goal_conceded"][0]
    assert conceded[2] == pytest.approx(-0.865)  # spec: a routine shot costs about -0.87


def test_marking_denial_is_capped():
    events = [ev(i, i * 300, "marking_denial", "azc_04", "rdm_09") for i in range(1, 12)]
    total = sum(e["delta"] for e in rate(events))
    assert total == pytest.approx(RC.MARKING_DENIAL_CAP, abs=0.01)


def test_counterpress_definition():
    events = [ev(1, 103, "pressure", "azc_08", "rdm_06"), ev(2, 120, "pressure", "azc_08", "rdm_06")]
    turnovers = [(100, 0, None, None, "open")]  # Azure lost the ball at 100 s
    offball.counterpresses(events, turnovers)
    assert [e["type"] for e in events] == ["counterpress", "pressure"]


def test_big_chance_missed_definition():
    shots = [ev(1, 10, "shot", "azc_09", xg=0.3, outcome="off_target"), ev(2, 20, "shot", "azc_09", xg=0.3, outcome="saved"),
             ev(3, 30, "shot", "azc_09", xg=0.1, outcome="post")]
    missed = offball.big_chances_missed(shots)
    assert [m["t"] for m in missed] == [10.0]


@pytest.fixture(scope="module")
def match():
    return build_match(load_world(ROOT / "data" / "world.json"), MatchInfo("test", 21, "Test", 1))


def test_full_match_rating_log(match):
    events = {e.id: e for e in match.events.events}
    running = {}
    for r in match.ratings.entries:
        assert r.event_id in events
        assert events[r.event_id].t == r.t
        running[r.player] = running.get(r.player, 6.0) + r.delta
        assert abs(running[r.player] - r.rating_after) <= 0.01
        assert 3.1 <= r.rating_after <= 9.9


def test_every_player_logged_at_least_every_45_seconds(match):
    sent_off = match.result.sent_off
    for team in match.meta.teams:
        for p in team.players:
            times = [0.0] + [r.t for r in match.ratings.entries if r.player == p.id]
            end = min(sent_off.get(p.id, 5400), 5400)
            times = [t for t in times if t <= end]
            gaps = [b - a for a, b in zip(times, times[1:])] + [end - times[-1]]
            assert max(gaps) <= 45, p.id


def test_off_ball_credit_exists_and_is_flagged(match):
    off = [r for r in match.ratings.entries if r.off_ball]
    assert {r.reason_code for r in off} >= {"pressure_regain", "counterpress"}
    assert all(r.reason_code in RC.OFF_BALL for r in off)
