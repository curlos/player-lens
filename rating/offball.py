"""Off-ball detection: derive credit events from simulator events plus recorded positions and activities.

Definitions (specs/rating-model.md; thresholds in rating/config.py):
- Counterpress: a pressure within 5 s of our own turnover (the pressure event is retyped).
- Pressure regain: our team wins the ball back in open play within 5 s of the player's pressure, with
  the presser still within 10 m of the ball.
- Recovery run: after our turnover, a player who was ahead of the ball tracks back (activity
  ``track_back`` for 3+ s) at least 12 m and ends goal-side of the ball within 8 s.
- Marking denial: in a 5-minute window, a defender stays within 2.5 m of the same opponent for at
  least half of the opponent's open-play possession seconds, and that opponent receives no pass.
- Decoy run: a ``make_run`` of 3+ s drags the nearest defender (still within 5 m, moved 6+ m) while a
  teammate receives a pass with 4+ m of space.
- Big chance missed: a shot with xG 0.25 or more that goes off target or hits the post or bar.
- Error leading to goal: the opponent scores within 10 s of winning the ball from our player in our
  defensive zone (last error); up to two earlier such turnovers in the same 10 s are earlier errors.

All derived events carry ``_phase = 1`` so they sort after simulator events at the same second.
"""

from __future__ import annotations

from collections import Counter
from typing import Any

import numpy as np

from rating import config as RC
from sim import config as C
from sim.engine import ACT_INDEX, MatchResult

Event = dict[str, Any]
SIDES = ("azc", "rdm")


def _side(pid: str) -> int:
    return 0 if pid.startswith("azc") else 1


def _advance(x: np.ndarray | float, side: int):
    return x if side == 0 else C.PITCH_L - x


def _event(t: float, etype: str, player: str, *, other: str | None = None, frm=None, to=None,
           related: list[Event] | None = None, **extra: Any) -> Event:
    ev: Event = {"t": float(t), "type": etype, "team": SIDES[_side(player)], "player": player, "other": other,
                 "from": None if frm is None else (round(float(frm[0]), 1), round(float(frm[1]), 1)),
                 "to": None if to is None else (round(float(to[0]), 1), round(float(to[1]), 1)),
                 "outcome": "success", "xg": None, "speed_kmh": None, "related": related or [], "_phase": 1}
    ev.update(extra)
    return ev


class Tracks:
    """Positions (meters) and activities as numpy arrays, plus per-second possession and open play."""

    def __init__(self, r: MatchResult):
        self.pos = {pid: np.asarray(xy, dtype=float).reshape(-1, 2) / 10.0 for pid, xy in r.xy.items()}
        self.act = {pid: np.asarray(a) for pid, a in r.act.items()}
        self.n = len(self.pos["ball"])
        self.side_at = np.full(self.n, -1, dtype=int)
        for i, (t, side, *_rest) in enumerate(r.possessions):
            end = r.possessions[i + 1][0] if i + 1 < len(r.possessions) else self.n
            self.side_at[t:end] = side
        any_player = next(iter(r.shape_dev))
        self.open_play = np.asarray(r.shape_dev[any_player]) >= 0
        self.on_until = {pid: r.sent_off.get(pid, self.n) for pid in r.shape_dev}
        self.players = [pid for pid in r.entity_order if pid not in ("ref", "ball")]

    def outfield(self, side: int, t: int) -> list[str]:
        return [p for p in self.players if _side(p) == side and not p.endswith("_01") and self.on_until[p] > t]


def _turnovers(r: MatchResult) -> list[tuple[int, int, Any, Any, str]]:
    """Possession changes: (t, side that lost the ball, cause, culprit, kind)."""
    out = []
    for prev, cur in zip(r.possessions, r.possessions[1:]):
        if prev[1] != cur[1]:
            out.append((cur[0], prev[1], cur[2], cur[3], cur[4]))
    return out


def counterpresses(events: list[Event], turnovers: list) -> None:
    """Retype pressures made within COUNTERPRESS_WINDOW_S of the presser's team losing the ball."""
    lost = {0: [], 1: []}
    for t, side, *_ in turnovers:
        lost[side].append(t)
    for e in events:
        if e["type"] != "pressure":
            continue
        side = _side(e["player"])
        if any(0 <= e["t"] - t0 <= RC.COUNTERPRESS_WINDOW_S for t0 in lost[side]):
            e["type"] = "counterpress"


def pressure_regains(events: list[Event], r: MatchResult, tr: Tracks) -> list[Event]:
    gains = [(t, side, cause) for (t, side, cause, _c, kind) in r.possessions if kind == "open"]
    out, seen = [], set()
    for e in events:
        if e["type"] not in ("pressure", "counterpress"):
            continue
        side, t = _side(e["player"]), int(e["t"])
        if tr.side_at[t] == side:
            continue
        for t1, gside, cause in gains:
            if t < t1 <= t + RC.REGAIN_WINDOW_S and gside == side:
                key = (e["player"], t1)
                near = float(np.hypot(*(tr.pos[e["player"]][t1] - tr.pos["ball"][t1]))) <= RC.REGAIN_NEAR_M
                if near and key not in seen:
                    seen.add(key)
                    p = tr.pos[e["player"]][t1]
                    rel = [e] + ([cause] if cause is not None else [])
                    out.append(_event(t1, "pressure_regain", e["player"], other=e["other"], frm=p, related=rel))
                break
            if t1 > t + RC.REGAIN_WINDOW_S:
                break
    return out


def recovery_runs(turnovers: list, tr: Tracks) -> list[Event]:
    out = []
    track = ACT_INDEX["track_back"]
    for t0, side, cause, _c, kind in turnovers:
        if kind != "open" or t0 >= tr.n - 2:
            continue
        ball0 = _advance(tr.pos["ball"][t0][0], side)
        for pid in tr.outfield(side, t0):
            p = tr.pos[pid]
            if _advance(p[t0][0], side) - ball0 <= RC.RECOVERY_AHEAD_M:
                continue
            end = min(tr.n - 1, t0 + RC.RECOVERY_WINDOW_S)
            tracked = int(np.sum(tr.act[pid][t0:end + 1] == track))
            if tracked < RC.RECOVERY_MIN_TRACK_S:
                continue
            for t in range(t0 + 1, end + 1):
                back = _advance(p[t0][0], side) - _advance(p[t][0], side)
                goal_side = _advance(p[t][0], side) < _advance(tr.pos["ball"][t][0], side)
                if back >= RC.RECOVERY_MIN_RUN_M and goal_side:
                    out.append(_event(t, "recovery_run", pid, frm=p[t0], to=p[t], related=[cause] if cause else [],
                                      _values={"distance_m": int(round(float(np.hypot(*(p[t] - p[t0])))))}))
                    break
    return out


def marking_denials(events: list[Event], tr: Tracks) -> list[Event]:
    out = []
    received = Counter()
    passes = [(int(e["t"]), e["other"]) for e in events
              if e["type"] in ("pass", "key_pass") and e["outcome"] == "success" and e["other"]]
    for w0 in range(0, tr.n - 1, RC.MARKING_WINDOW_S):
        w1 = min(tr.n - 1, w0 + RC.MARKING_WINDOW_S)
        received.clear()
        for t, who in passes:
            if w0 <= t < w1:
                received[who] += 1
        for att_side in (0, 1):
            secs = np.nonzero((tr.side_at[w0:w1] == att_side) & tr.open_play[w0:w1])[0] + w0
            if len(secs) < RC.MARKING_MIN_SECONDS:
                continue
            attackers = tr.outfield(att_side, w1)
            defenders = tr.outfield(1 - att_side, w1)
            if not attackers or not defenders:
                continue
            A = np.stack([tr.pos[a][secs] for a in attackers])  # (na, s, 2)
            for d in defenders:
                D = tr.pos[d][secs]  # (s, 2)
                dist = np.hypot(*(A - D[None, :, :]).transpose(2, 0, 1))  # (na, s)
                tight_each = dist <= RC.MARKING_TIGHT_M  # per attacker: seconds this defender was tight on them
                k = int(tight_each.sum(axis=1).argmax())  # the opponent marked most (first on ties)
                tight = tight_each[k]
                if tight.sum() < RC.MARKING_MIN_SECONDS or tight.mean() < RC.MARKING_MIN_SHARE:
                    continue
                main = attackers[k]
                if received[main] == 0:
                    out.append(_event(w1, "marking_denial", d, other=main, frm=tr.pos[d][w1],
                                      _values={"seconds": int(tight.sum())}))
    return out


def decoy_runs(events: list[Event], tr: Tracks) -> list[Event]:
    out = []
    run = ACT_INDEX["make_run"]
    passes = [e for e in events if e["type"] in ("pass", "key_pass") and e["outcome"] == "success" and e["other"]]
    for pid in tr.players:
        if pid.endswith("_01"):
            continue
        side = _side(pid)
        acts = tr.act[pid]
        is_run = (acts == run) & (tr.side_at == side)
        last_credit = -10**9
        t = 0
        while t < tr.n:
            if not is_run[t]:
                t += 1
                continue
            s = t
            while t < tr.n and is_run[t]:
                t += 1
            e = t - 1
            if e - s + 1 < RC.DECOY_MIN_RUN_S or s - last_credit < RC.DECOY_COOLDOWN_S:
                continue
            opp = tr.outfield(1 - side, s)
            if not opp:
                continue
            ds = [float(np.hypot(*(tr.pos[o][s] - tr.pos[pid][s]))) for o in opp]
            k = int(np.argmin(ds))
            dfn = opp[k]
            if ds[k] > RC.DECOY_DRAG_M:
                continue
            if float(np.hypot(*(tr.pos[dfn][e] - tr.pos[pid][e]))) > RC.DECOY_DRAG_M:
                continue
            if float(np.hypot(*(tr.pos[dfn][e] - tr.pos[dfn][s]))) < RC.DECOY_DEFENDER_MOVE_M:
                continue
            for pe in passes:
                pt = int(pe["t"])
                if not (s <= pt <= e + 2) or _side(pe["player"]) != side or pe["other"] == pid:
                    continue
                rx = tr.pos[pe["other"]][pt]
                space = min(float(np.hypot(*(tr.pos[o][pt] - rx))) for o in opp)
                if space >= RC.DECOY_FREE_RECEIVER_M:
                    out.append(_event(pt, "decoy_run", pid, other=dfn, frm=tr.pos[pid][s], to=tr.pos[pid][pt],
                                      related=[pe], _values={"teammate": pe["other"]}))
                    last_credit = s
                    break
    return out


def big_chances_missed(events: list[Event]) -> list[Event]:
    return [_event(e["t"], "big_chance_missed", e["player"], frm=e["from"], related=[e], xg=e["xg"])
            for e in events if e["type"] == "shot" and (e["xg"] or 0) >= RC.BIG_CHANCE_XG
            and e["outcome"] in ("off_target", "post")]


def errors_leading_to_goal(events: list[Event], r: MatchResult) -> list[Event]:
    out = []
    for g in (e for e in events if e["type"] == "goal"):
        side = _side(g["player"])
        tg = g["t"]
        chain = [p for p in r.possessions if tg - RC.ERROR_WINDOW_S <= p[0] <= tg and p[1] == side
                 and p[4] == "open" and p[3] is not None and p[2] is not None]
        current = [p for p in r.possessions if p[0] <= tg]
        if not chain or not current or current[-1] is not chain[-1]:
            continue  # the scoring possession did not start from an error
        errs = []
        for t0, _s, cause, culprit, _k in reversed(chain):
            fx = cause["from"][0] if cause.get("from") else None
            own_line_dist = None if fx is None else (fx if _side(culprit) == 0 else C.PITCH_L - fx)
            if own_line_dist is not None and own_line_dist <= RC.ERROR_ZONE_M:
                errs.append((culprit, cause))
        for rank, (culprit, cause) in enumerate(errs[:3]):
            out.append(_event(tg, "error_leading_to_goal", culprit, related=[cause, g], outcome="none",
                              _rank="last" if rank == 0 else "earlier"))
    return out


def derive(r: MatchResult) -> list[Event]:
    """Retype counterpresses in place and return the new off-ball and derived events."""
    events = r.events
    tr = Tracks(r)
    turnovers = _turnovers(r)
    counterpresses(events, turnovers)
    new: list[Event] = []
    new += pressure_regains(events, r, tr)
    new += recovery_runs(turnovers, tr)
    new += marking_denials(events, tr)
    new += decoy_runs(events, tr)
    new += big_chances_missed(events)
    new += errors_leading_to_goal(events, r)
    for i, e in enumerate(new):
        e["_seq"] = i
        e["outcome"] = e.get("outcome", "success")
    return new
