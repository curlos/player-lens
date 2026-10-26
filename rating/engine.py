"""Rating engine: turns events into the rating log (specs/rating-model.md, specs/match-files.md).

Pure code. Every entry stores the raw delta (after repeat decay), the soft-cap scale and the final
delta, so a player's rating at time t is 6.0 plus the sum of their deltas up to t.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any

import numpy as np

from rating import config as RC
from sim.engine import ACT_INDEX, MatchResult

Event = dict[str, Any]
Credit = tuple[str, str, float, dict]  # (player, reason_code, base delta, values)

_LAZY = {ACT_INDEX["stand"], ACT_INDEX["walk"]}
_WORKING = {ACT_INDEX[a] for a in ("jog", "run", "sprint", "press", "track_back", "mark", "make_run", "carry")}


def keeper_of(team: str) -> str:
    return f"{team}_01"


def credits(ev: Event) -> list[Credit]:
    """The rating credits one event produces, in a fixed order. Empty for events that never rate."""
    t, p, o = ev["type"], ev["player"], ev.get("other")
    vals = dict(ev.get("_values") or {})
    xg = ev.get("xg")
    out: list[Credit] = []
    if t == "key_pass":
        out.append((p, "key_pass", RC.DELTAS["key_pass"], {"receiver": o} if o else {}))
    elif t == "shot" and ev["outcome"] in ("saved", "goal"):
        out.append((p, "shot_on_target", RC.DELTAS["shot_on_target"], {"xg": xg}))
    elif t == "goal":
        out.append((p, "goal", RC.DELTAS["goal"], {"xg": xg}))
        if o:
            out.append((o, "assist", RC.DELTAS["assist"], {"scorer": p}))
        other_team = "rdm" if ev["team"] == "azc" else "azc"
        out.append((keeper_of(other_team), "gk_goal_conceded",
                    -(RC.GK_CONCEDED_BASE + RC.GK_CONCEDED_XG * (1.0 - (xg or 0.0))), {"xg": xg, "scorer": p}))
    elif t == "save":
        out.append((p, "gk_save", min(RC.GK_SAVE_CAP, RC.GK_SAVE_BASE + RC.GK_SAVE_XG * (xg or 0.0)),
                    {"xg": xg, "shooter": o}))
    elif t == "tackle":
        out.append((p, "tackle", RC.DELTAS["tackle"], {"opponent": o}))
        out.append((o, "dispossessed", RC.DELTAS["dispossessed"], {"opponent": p}))
    elif t == "interception":
        out.append((p, "interception", RC.DELTAS["interception"], {"passer": o} if o else {}))
    elif t == "block":
        out.append((p, "block", RC.DELTAS["block"], {"shooter": o} if o else {}))
    elif t == "clearance":
        out.append((p, "clearance", RC.DELTAS["clearance"], {}))
    elif t == "aerial_duel":
        out.append((p, "aerial_duel_won", RC.DELTAS["aerial_duel_won"], {"opponent": o} if o else {}))
    elif t == "dribble":
        out.append((p, "dribble", RC.DELTAS["dribble"], {"opponent": o}))
        out.append((o, "beaten_by_dribble", RC.DELTAS["beaten_by_dribble"], {"opponent": p}))
    elif t == "foul":
        out.append((p, "foul_committed", RC.DELTAS["foul_committed"], {"opponent": o}))
        out.append((o, "foul_won", RC.DELTAS["foul_won"], {"opponent": p}))
    elif t in ("handball", "offside", "card_yellow", "card_red", "big_chance_missed", "gk_claim", "gk_sweep",
               "counterpress", "pressure_regain", "recovery_run", "decoy_run", "marking_denial"):
        if t == "big_chance_missed":
            vals["xg"] = xg
        if o and t in ("pressure_regain", "counterpress", "decoy_run", "marking_denial", "gk_claim", "gk_sweep"):
            vals["opponent"] = o
        out.append((p, t, RC.DELTAS[t], vals))
    elif t == "error_leading_to_goal":
        code = "error_leading_to_goal" if ev.get("_rank") == "last" else "error_leading_to_goal_earlier"
        out.append((p, code, RC.DELTAS[code], {}))
    elif t == "shape_check":
        reason = ev["_shape_reason"]
        out.append((p, reason, RC.SHAPE_DELTAS[reason], vals))
    return [c for c in out if c[0]]


def _interval(player: str, k: int) -> int:
    """Deterministic 30-45 s spacing for a player's k-th shape check (no RNG needed)."""
    number = int(player.split("_")[1])
    return RC.SHAPE_INTERVAL_MIN + (number * 7 + k * 11 + (3 if player.startswith("rdm") else 0)) % RC.SHAPE_INTERVAL_SPAN


def _shape_reason(pid: str, t0: int, t1: int, r: MatchResult) -> tuple[str, dict]:
    """Judge the window (t0, t1]: position vs the shape target, work rate, and walking when out of position."""
    if pid.endswith("_01"):
        return "shape_no_change", {}
    dev = np.asarray(r.shape_dev[pid][t0 + 1:t1 + 1])
    acts = np.asarray(r.act[pid][t0 + 1:t1 + 1])
    mask = dev >= 0
    if mask.sum() < 5:
        return "shape_no_change", {}
    mean_dev = float(dev[mask].mean())
    working = float(np.isin(acts[mask], list(_WORKING)).mean())
    lazy_far = float((np.isin(acts[mask], list(_LAZY)) & (dev[mask] > RC.SHAPE_WALK_DEV_M)).mean())
    values = {"deviation_m": round(mean_dev, 1)}
    if lazy_far >= RC.SHAPE_WALK_SHARE:
        return "shape_walking", values
    if mean_dev > RC.SHAPE_OUT_DEV_M:
        return "shape_out_of_position", values
    if mean_dev <= RC.SHAPE_KEPT_DEV_M and working >= RC.SHAPE_KEPT_MIN_WORK:
        return "shape_kept", values
    return "shape_no_change", values


def shape_checks(events: list[Event], r: MatchResult, duration: int) -> list[Event]:
    """Add a shape_check event wherever a player would otherwise go 30-45 s without a rating entry."""
    times: dict[str, list[float]] = defaultdict(list)
    marking_count: dict[str, int] = defaultdict(int)
    max_marking = int(round(RC.MARKING_DENIAL_CAP / RC.DELTAS["marking_denial"]))
    for ev in events:
        for pid, code, _d, _v in credits(ev):
            if code == "marking_denial":
                marking_count[pid] += 1
                if marking_count[pid] > max_marking:
                    continue
            times[pid].append(ev["t"])
    out: list[Event] = []
    for pid in r.shape_dev:
        off_at = r.sent_off.get(pid, duration + 1)
        marks = sorted(t for t in times[pid] if t < off_at) + [min(off_at, duration + 1)]
        last, k = 0, 0
        for nxt in marks:
            while nxt - last > _interval(pid, k):
                t = last + _interval(pid, k)
                if t >= off_at or t > duration:
                    break
                reason, values = _shape_reason(pid, int(last), int(t), r)
                xy = r.xy[pid]
                ti = int(t)
                out.append({"t": float(t), "type": "shape_check", "team": pid[:3], "player": pid, "other": None,
                            "from": (xy[2 * ti] / 10.0, xy[2 * ti + 1] / 10.0), "to": None, "outcome": "none",
                            "xg": None, "speed_kmh": None, "related": [], "_phase": 2, "_seq": len(out),
                            "_shape_reason": reason, "_values": values})
                last, k = t, k + 1
            last = max(last, nxt)
    return out


def _soft_cap(rating: float, raw: float) -> float:
    """Scale factor: gains shrink near the top, losses near the bottom; also keeps the rating in 3.1-9.9."""
    if raw > 0:
        scale = min(1.0, (RC.SOFT_CAP_TOP - rating) / RC.SOFT_CAP_SPAN)
        if rating + raw * scale > RC.MAX_RATING:
            scale = max(0.0, (RC.MAX_RATING - rating) / raw)
    elif raw < 0:
        scale = min(1.0, (rating - RC.SOFT_CAP_BOTTOM) / RC.SOFT_CAP_SPAN)
        if rating + raw * scale < RC.MIN_RATING:
            scale = max(0.0, (rating - RC.MIN_RATING) / -raw)
    else:
        scale = 1.0
    return max(0.0, min(1.0, scale))


def rate(events: list[Event]) -> list[dict]:
    """Walk the time-ordered events (each already has an ``id``) and return the rating log entries."""
    rating: dict[str, float] = defaultdict(lambda: RC.START)
    seen: dict[tuple[str, str], int] = defaultdict(int)
    marking_total: dict[str, float] = defaultdict(float)
    entries: list[dict] = []
    for ev in events:
        for pid, code, base, values in credits(ev):
            if code == "marking_denial":
                if marking_total[pid] >= RC.MARKING_DENIAL_CAP - 1e-9:
                    continue
                marking_total[pid] += base
            n = seen[(pid, code)]
            seen[(pid, code)] += 1
            decay = 1.0 if (code in RC.NO_DECAY or base <= 0) else max(RC.REPEAT_DECAY_FLOOR, RC.REPEAT_DECAY_BASE ** n)
            raw = round(base * decay, 3)
            before = rating[pid]
            scale = round(_soft_cap(before, raw), 3)
            delta = round(raw * scale, 2)
            after = round(before + delta, 2)
            if after > RC.MAX_RATING or after < RC.MIN_RATING:  # rounding guard
                delta = round((RC.MAX_RATING if after > RC.MAX_RATING else RC.MIN_RATING) - before, 2)
                after = round(before + delta, 2)
            rating[pid] = after
            entries.append({
                "id": f"r_{len(entries) + 1:04d}", "t": ev["t"], "player": pid, "event_id": ev["id"],
                "raw_delta": raw, "scale": scale, "delta": delta, "rating_after": after, "reason_code": code,
                "values": {k: v for k, v in values.items() if v is not None},
                "off_ball": code in RC.OFF_BALL,
            })
    return entries


def importance(ev: Event, score_before: tuple[int, int], max_abs_delta: float, title_decider: bool) -> float:
    """Event importance 0-1: base weight by type, times context, nudged by the rating change (code only)."""
    t = ev["type"]
    xg = ev.get("xg") or 0.0
    if t == "shot":
        base = min(0.75, 0.2 + 0.8 * xg) if ev["outcome"] != "goal" else 0.95
    elif t == "save":
        base = min(0.8, 0.3 + 0.6 * xg)
    elif t == "free_kick" and ev.get("_attacking_third"):
        base = 0.3
    else:
        base = RC.IMPORTANCE_BASE.get(t, 0.05)
    mult = 1.0
    if ev["t"] >= RC.IMPORTANCE_LATE_T:
        mult *= RC.IMPORTANCE_LATE
    if abs(score_before[0] - score_before[1]) <= 1:
        mult *= RC.IMPORTANCE_CLOSE
    if title_decider:
        mult *= RC.IMPORTANCE_TITLE
    value = base * mult + min(RC.IMPORTANCE_DELTA_CAP, RC.IMPORTANCE_DELTA_K * max_abs_delta)
    if t == "goal":
        value = 1.0
    return round(min(1.0, max(0.0, value)), 2)
