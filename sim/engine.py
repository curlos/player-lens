"""Match engine: one seeded, deterministic 90-minute simulation at 1 Hz.

Tick order (specs/simulator-movement.md): (1) possession and ball state, (2) every player picks a target,
(3) every player moves via move_player(), (4) fatigue, (5) activity labels, (6) referee and ball,
(7) snapshot. One numpy Generator, passed in by seed, is the only source of randomness.

The engine emits raw events (passes, shots, duels, fouls, restarts, pressures...). Off-ball credit
(counterpress, pressure regain, recovery and decoy runs, marking denial, shape checks) is derived
afterwards by rating/offball.py from these events plus the recorded positions and activities.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from sim import config as C
from sim import possession as P
from sim import rules as R
from sim.models import Position, World
from sim.movement import (
    Ball,
    Body,
    clamp_to_pitch,
    move_ball_toward,
    move_player,
    place_ball,
    place_body,
    player_accel,
    player_speed,
    speed_label,
    update_fatigue,
)

ACTIVITIES = [
    "stand", "walk", "jog", "run", "sprint", "carry", "press", "track_back", "mark", "make_run", "hold_shape",
    "talk_ref", "huddle", "celebrate", "down", "wall", "set_piece_wait", "take_set_piece", "sent_off",
]
ACT_INDEX = {a: i for i, a in enumerate(ACTIVITIES)}
OVERRIDE_ACTIVITIES = {"carry", "celebrate", "huddle", "talk_ref", "down", "wall", "set_piece_wait",
                       "take_set_piece", "sent_off"}
MOVING_ACTIVITIES = {"press", "track_back", "make_run"}
RUNNER_POSITIONS = {Position.ST: 1.0, Position.W: 1.0, Position.AM: 0.7, Position.CM: 0.4, Position.FB: 0.35}
SUPPORT_POSITIONS = {Position.DM, Position.CM, Position.AM}

Event = dict[str, Any]


class PlayerState(Body):
    """A player's live state. Positions and velocities are written only by sim.movement."""

    def __init__(self, player, side: int, formation: str):
        attrs = player.attributes.model_dump(exclude_none=True)
        super().__init__(player.id, player_speed(attrs["pace"]), player_accel(attrs["pace"]))
        self.team = player.team
        self.side = side
        self.dir = 1 if side == 0 else -1
        self.number = player.number
        self.position = player.position
        self.is_gk = player.position == Position.GK
        self.attrs = attrs
        self.temperament = player.temperament.value
        self.slot_xy = C.FORMATION_XY[formation][player.number]
        self.on_pitch = True
        self.yellows = 0
        self.intent = "hold_shape"
        self.tx = self.ty = 0.0
        self.shape_x = self.shape_y = 0.0
        self.run_until = -1
        self.run_tx = self.run_ty = 0.0
        self.press_since = -1
        self.press_cool_until = -1
        self.beaten_until = -1
        self.last_pressure_t = -99
        self.last_pressure_on = ""
        self.override: str | None = None
        self.override_until = -1
        self.override_target: Any = None
        self.carry_tx = self.carry_ty = 0.0


@dataclass
class Flight:
    kind: str  # pass, shot, clear
    sx: float
    sy: float
    ex: float
    ey: float
    depart: int
    arrive: int
    result: str
    side: int
    passer: PlayerState | None = None
    receiver: PlayerState | None = None
    winner: PlayerState | None = None
    loser: PlayerState | None = None
    cross: bool = False
    pass_event: Event | None = None


@dataclass
class Restart:
    type: str
    side: int
    sx: float
    sy: float
    ready_at: int
    taker: PlayerState
    direct: bool = False
    fouled: str | None = None
    card: bool = False


@dataclass
class MatchResult:
    """Everything later steps need: raw events, recorded tracks and a few logs for off-ball detection."""

    seed: int
    events: list[Event]
    entity_order: list[str]
    xy: dict[str, list[int]]
    act: dict[str, list[int]]
    shape_dev: dict[str, list[float]]
    possessions: list[tuple[int, int, Event | None, str | None, str]]  # (t, side, cause event, culprit id, "open"|"restart")
    score: list[int]
    sent_off: dict[str, int] = field(default_factory=dict)
    players: dict[str, PlayerState] = field(default_factory=dict)


class Match:
    """One simulated match. Construct with the world and a seed, then call run()."""

    def __init__(self, world: World, seed: int, tactics: dict | None = None):
        self.seed = seed
        self.rng = np.random.default_rng(seed)
        self.tactics = tactics or C.TEAM_TACTICS
        teams = sorted(world.teams, key=lambda tm: tm.id != "azc")  # azc first, attacks left to right
        self.team_ids = [tm.id for tm in teams]
        self.sides: list[list[PlayerState]] = []
        for side, tm in enumerate(teams):
            self.sides.append([PlayerState(p, side, tm.formation) for p in sorted(tm.players, key=lambda q: q.number)])
        self.players = self.sides[0] + self.sides[1]
        self.by_id = {p.id: p for p in self.players}
        self.ref = Body("ref", C.REF_SPEED, C.REF_ACCEL)
        self.ball = Ball()
        self.entity_order = [p.id for p in self.players] + ["ref", "ball"]
        self.xy: dict[str, list[int]] = {e: [] for e in self.entity_order}
        self.act: dict[str, list[int]] = {e: [] for e in self.entity_order if e != "ball"}
        self.shape_dev: dict[str, list[float]] = {p.id: [] for p in self.players}
        self.events: list[Event] = []
        self.possessions: list[tuple[int, int, Event | None, str | None, str]] = []
        self.score = [0, 0]
        self.sent_off: dict[str, int] = {}
        self.t = 0
        # Ball state
        self.state = "dead"
        self.carrier: PlayerState | None = None
        self.flight: Flight | None = None
        self.restart: Restart | None = None
        self.poss_side = 0
        self.last_touch_side = 0
        self.next_decision = 0
        self.last_decision = -1
        self.last_pass: tuple[PlayerState, PlayerState, int, Event] | None = None
        self.celebration: dict | None = None
        self.header_pending = False

    # ------------------------------------------------------------------ helpers
    def tac(self, side: int, key: str) -> Any:
        return self.tactics[self.team_ids[side]][key]

    def on_pitch(self, side: int) -> list[PlayerState]:
        return [p for p in self.sides[side] if p.on_pitch]

    def keeper(self, side: int) -> PlayerState:
        return next(p for p in self.sides[side] if p.is_gk)

    def uniform(self, lo: float, hi: float) -> float:
        return float(lo + (hi - lo) * self.rng.random())

    def randint(self, lo: int, hi: int) -> int:
        return int(self.rng.integers(lo, hi + 1))

    def emit(self, etype: str, player: PlayerState, *, other: PlayerState | None = None, frm=None, to=None,
             outcome: str = "none", xg: float | None = None, speed_kmh: float | None = None,
             related: list[Event] | None = None, team_side: int | None = None) -> Event:
        ev: Event = {
            "t": float(self.t), "type": etype, "team": self.team_ids[player.side if team_side is None else team_side],
            "player": player.id, "other": other.id if other else None,
            "from": None if frm is None else (round(frm[0], 1), round(frm[1], 1)),
            "to": None if to is None else (round(to[0], 1), round(to[1], 1)),
            "outcome": outcome, "xg": None if xg is None else round(xg, 3),
            "speed_kmh": None if speed_kmh is None else round(speed_kmh, 1),
            "related": related or [], "_seq": len(self.events),
        }
        self.events.append(ev)
        return ev

    # ------------------------------------------------------------------ run
    def run(self) -> MatchResult:
        self._setup_kickoff_layout(kicking_side=0)
        self.restart = Restart("kickoff", 0, C.PITCH_L / 2, C.PITCH_W / 2, 1, self._kicker(0))
        self._record()
        for t in range(1, C.DURATION_S + 1):
            self.t = t
            self._tick()
        return MatchResult(
            seed=self.seed, events=self.events, entity_order=self.entity_order, xy=self.xy, act=self.act,
            shape_dev=self.shape_dev, possessions=self.possessions, score=list(self.score),
            sent_off=dict(self.sent_off), players=self.by_id,
        )

    def _tick(self) -> None:
        self._step_possession()  # (1)
        self._pick_targets()  # (2)
        speeds = {}
        for p in self.players:  # (3)
            speeds[p.id] = move_player(p, p.tx, p.ty, self._speed_cap(p))
        for p in self.players:  # (4)
            update_fatigue(p, speeds[p.id], p.attrs["work_rate"], p.attrs["stamina"])
        acts = {p.id: self._activity(p, speeds[p.id]) for p in self.players}  # (5)
        self._move_ref_and_ball()  # (6)
        self._record(acts)  # (7)

    def _record(self, acts: dict[str, str] | None = None) -> None:
        for p in self.players:
            self.xy[p.id] += [int(round(p.x * 10)), int(round(p.y * 10))]
            self.act[p.id].append(ACT_INDEX[acts[p.id]] if acts else ACT_INDEX["stand"])
        self.xy["ref"] += [int(round(self.ref.x * 10)), int(round(self.ref.y * 10))]
        self.act["ref"].append(ACT_INDEX[speed_label(self.ref.speed)])
        self.xy["ball"] += [int(round(self.ball.x * 10)), int(round(self.ball.y * 10))]
        open_play = self.state != "dead"
        for p in self.players:
            dev = math.hypot(p.x - p.shape_x, p.y - p.shape_y) if (open_play and p.on_pitch) else -1.0
            self.shape_dev[p.id].append(round(dev, 1))

    # ------------------------------------------------------------------ layouts
    def _team_point(self, side: int, depth: float, y_team: float) -> tuple[float, float]:
        """Convert team-frame (depth from own goal line, y with the team facing its attack) to pitch meters."""
        if side == 0:
            return depth, y_team
        return C.PITCH_L - depth, C.PITCH_W - y_team

    def _kicker(self, side: int) -> PlayerState:
        team = self.on_pitch(side)
        for n in (9, 10, 8):
            for p in team:
                if p.number == n:
                    return p
        return next(p for p in team if not p.is_gk)

    def _kickoff_xy(self, p: PlayerState, kicking_side: int) -> tuple[float, float]:
        sx, sy = p.slot_xy
        depth = 2.0 + sx * 48.0
        y = sy * C.PITCH_W
        if p.side == kicking_side and p is self._kicker(kicking_side):
            depth, y = C.PITCH_L / 2 - 0.4, C.PITCH_W / 2
        return self._team_point(p.side, depth, y)

    def _setup_kickoff_layout(self, kicking_side: int) -> None:
        for p in self.players:
            place_body(p, *self._kickoff_xy(p, kicking_side))
            p.shape_x, p.shape_y = p.x, p.y
        place_body(self.ref, C.PITCH_L / 2 - 4.0, C.PITCH_W / 2 + 12.0)
        place_ball(self.ball, C.PITCH_L / 2, C.PITCH_W / 2)

    # ------------------------------------------------------------------ (1) possession
    def _ball_point(self) -> tuple[float, float]:
        if self.state == "flight" and self.flight:
            return self.flight.ex, self.flight.ey
        if self.state == "dead" and self.restart:
            return self.restart.sx, self.restart.sy
        return self.ball.x, self.ball.y

    def _step_possession(self) -> None:
        t = self.t
        if self.state == "dead":
            r = self.restart
            if r and t >= r.ready_at:
                near = math.hypot(r.taker.x - r.sx, r.taker.y - r.sy) <= 2.5
                if near or t >= r.ready_at + 12:
                    self._take_restart()
            return
        if self.state == "flight" and self.flight and t >= self.flight.arrive:
            self._resolve_flight()
        if self.state == "loose":
            self._resolve_loose()
        if self.state == "carried" and self.carrier:
            self._carrier_step()

    def _give_ball(self, p: PlayerState, cause: Event | None = None, culprit: str | None = None,
                   kind: str = "open") -> None:
        self.state = "carried"
        self.carrier = p
        self.flight = None
        self.last_touch_side = p.side
        if p.side != self.poss_side or not self.possessions:
            self.possessions.append((self.t, p.side, cause, culprit, kind))
            self.poss_side = p.side
            self.last_pass = None
        lo, hi = C.DECISION_INTERVAL
        tempo = float(self.tac(p.side, "tempo"))
        self.next_decision = self.t + self.randint(lo, hi) - (1 if self.rng.random() < tempo * 0.5 else 0)
        p.carry_tx, p.carry_ty = self._carry_target(p)

    def _set_loose(self, x: float, y: float) -> None:
        self.state = "loose"
        self.carrier = None
        self.flight = None
        place_ball(self.ball, x, y)

    def _resolve_loose(self) -> None:
        bx, by = self.ball.x, self.ball.y
        best, best_key = None, None
        for p in self.players:
            if not p.on_pitch or p.override == "down":
                continue
            d = math.hypot(p.x - bx, p.y - by)
            if d <= 1.5:
                key = (d, -p.attrs["strength"], p.id)
                if best_key is None or key < best_key:
                    best, best_key = p, key
        if best is not None:
            culprit = None
            cause = None
            if best.side != self.poss_side and self.last_pass and self.last_pass[3]["outcome"] == "fail":
                culprit = self.last_pass[0].id
                cause = self.last_pass[3]
            self._give_ball(best, cause, culprit)

    def _opponents(self, p: PlayerState) -> list[PlayerState]:
        return self.on_pitch(1 - p.side)

    def _carrier_step(self) -> None:
        c = self.carrier
        assert c is not None
        t = self.t
        opps = self._opponents(c)
        nearest, nd = None, 1e9
        for o in opps:
            d = math.hypot(o.x - c.x, o.y - c.y)
            if (o.intent == "press" and d <= C.PRESSURE_RADIUS and o.speed >= C.PRESSURE_MIN_SPEED
                    and (o.last_pressure_on != c.id or t - o.last_pressure_t >= C.PRESSURE_REPEAT_S)):
                o.last_pressure_t, o.last_pressure_on = t, c.id
                self.emit("pressure", o, other=c, frm=(o.x, o.y), to=(c.x, c.y))
            if not o.is_gk and d < nd:
                nearest, nd = o, d
        if nearest is not None and nd <= C.TACKLE_RADIUS and t >= nearest.beaten_until:
            lo, k = C.TACKLE_ATTEMPT_P
            p_try = lo + k * float(self.tac(nearest.side, "press_intensity"))
            if nearest.intent != "press":
                p_try *= C.TACKLE_UNPRESSED
            if self.rng.random() < p_try:
                self._duel(nearest, c)
                if self.carrier is not c or self.state != "carried":
                    return
        if R.advance(c.x, c.dir) > C.PITCH_L - C.DANGER_ZONE_M:
            blocker = self._goal_side_blocker(c)
            if blocker is not None and t >= blocker.beaten_until and self.rng.random() < C.BLOCKER_DUEL_P:
                self._duel(blocker, c)
                if self.carrier is not c or self.state != "carried":
                    return
        if t >= self.next_decision or (nd < C.PRESSURED_DECISION_M and t > self.last_decision):
            self._decide(c)

    # ------------------------------------------------------------------ decisions
    def _pressure(self, x: float, y: float, side: int) -> float:
        return P.pressure_on(x, y, [(o.x, o.y) for o in self.on_pitch(1 - side)])

    def _carry_target(self, c: PlayerState) -> tuple[float, float]:
        opps = self._opponents(c)
        best, best_space = (c.x, c.y), -1.0
        if R.advance(c.x, c.dir) > C.PITCH_L - 14:  # near the byline: cut in toward goal
            gx = P.goal_x(c.dir) - c.dir * 8.0
            return clamp_to_pitch(gx, C.PITCH_W / 2 + (c.y - C.PITCH_W / 2) * 0.4, 1.0)
        angles = (0.0, 0.5, -0.5) if self._goal_side_blocker(c) is None else (1.1, -1.1, 2.2, -2.2)
        for ang in angles:
            dx = math.cos(ang) * 9.0 * c.dir
            dy = math.sin(ang) * 9.0 * (1 if c.dir > 0 else -1)
            tx, ty = clamp_to_pitch(c.x + dx, c.y + dy, 2.0)
            space = min((math.hypot(o.x - tx, o.y - ty) for o in opps), default=20.0)
            if ang != 0.0:
                space -= 0.8
            if space > best_space:
                best, best_space = (tx, ty), space
        return best

    def _goal_side_blocker(self, c: PlayerState) -> PlayerState | None:
        """Nearest defender standing goal-side in front of the carrier (within BLOCKER_M and a 45-degree cone)."""
        gx, gy = P.goal_x(c.dir), C.PITCH_W / 2
        hx, hy = gx - c.x, gy - c.y
        hn = math.hypot(hx, hy) or 1.0
        best, bd = None, C.BLOCKER_M
        for o in self._opponents(c):
            if o.is_gk:
                continue
            ox, oy = o.x - c.x, o.y - c.y
            d = math.hypot(ox, oy)
            if 0.1 < d < bd and (ox * hx + oy * hy) / (d * hn) > 0.7:
                best, bd = o, d
        return best

    def _pass_options(self, c: PlayerState, max_len: float = C.PASS_RANGE[1], backward_only: bool = False,
                      box_only: bool = False) -> list[dict]:
        opps = self._opponents(c)
        pressure = P.pressure_on(c.x, c.y, [(o.x, o.y) for o in opps])
        style = str(self.tac(c.side, "style"))
        out = []
        for m in self.on_pitch(c.side):
            if m is c or m.override == "down":
                continue
            ex, ey = clamp_to_pitch(m.x + m.vx, m.y + m.vy, 1.0)
            d = math.hypot(ex - c.x, ey - c.y)
            if d < C.PASS_RANGE[0] or d > max_len:
                continue
            progress = R.advance(ex, c.dir) - R.advance(c.x, c.dir)
            if backward_only and progress > 0:
                continue
            if box_only and not R.in_attacking_box(ex, ey, c.dir):
                continue
            lofted = d > C.LOFTED_DISTANCE or box_only
            gap, lane_def, lane_u = 0.0, None, 0.0
            for o in opps:
                dl, u = P.segment_distance(o.x, o.y, c.x, c.y, ex, ey)
                if 0.08 < u < 0.97 and dl < 2.5:
                    g = (2.5 - dl) * (0.4 if lofted else 1.0)
                    if g > gap:
                        gap, lane_def, lane_u = g, o, u
            marker = min(opps, key=lambda o: math.hypot(o.x - ex, o.y - ey)) if opps else None
            openness = math.hypot(marker.x - ex, marker.y - ey) if marker else 10.0
            final_third = R.advance(ex, c.dir) > 70 and progress > 0
            cross = (box_only or (R.advance(c.x, c.dir) > 70 and abs(c.y - C.PITCH_W / 2) > 18
                                  and R.in_attacking_box(ex, ey, c.dir)))
            pc = P.pass_completion(d, c.attrs["passing"], c.attrs["composure"], pressure, final_third, lofted, gap,
                                   openness, into_box=R.in_attacking_box(ex, ey, c.dir) and not R.in_attacking_box(c.x, c.y, c.dir))
            if cross:
                pc *= C.CROSS_COMPLETION
            gain = P.threat(ex, ey, c.dir) - P.threat(c.x, c.y, c.dir)
            score = (C.W_SAFE * pc + C.W_FORWARD[style] * progress / 10.0 + C.W_OPEN[style] * min(openness, 8.0) / 8.0
                     + C.W_THREAT * pc * gain * 10.0)
            if m.is_gk:
                score -= 0.8
            out.append({"kind": "pass", "score": score, "m": m, "ex": ex, "ey": ey, "d": d, "pc": pc,
                        "lofted": lofted or cross, "lane_def": lane_def, "lane_u": lane_u, "cross": cross,
                        "marker": marker if openness < C.RECEIVER_MARKED_M else None})
        out.sort(key=lambda o: -o["score"])
        return out[: C.PASS_CANDIDATES_BASE + c.attrs["vision"] // 25]

    def _decide(self, c: PlayerState, forced: str | None = None) -> None:
        self.last_decision = self.t
        opps = self._opponents(c)
        pressure = P.pressure_on(c.x, c.y, [(o.x, o.y) for o in opps])
        options: list[dict] = []
        if forced == "penalty":
            self._shoot(c, kind="penalty")
            return
        if forced == "header":
            x = P.xg(c.x, c.y, c.dir, pressure, header=True)
            if x >= 0.02 and self.rng.random() < min(C.HEADER_SHOT_MAX, C.HEADER_SHOT_BASE + C.HEADER_SHOT_XG * x):
                self._shoot(c, kind="header", xg_value=x)
                return
            forced = "throw_in"  # knock it down short
        if forced == "free_kick_direct":
            self._shoot(c, kind="free_kick")
            return
        if forced == "throw_in":
            options = self._pass_options(c, max_len=25.0)
        elif forced == "kickoff":
            options = self._pass_options(c, max_len=25.0, backward_only=True)
        elif forced == "corner":
            options = self._pass_options(c, max_len=50.0, box_only=True) or self._pass_options(c)
        elif forced in ("goal_kick", "free_kick"):
            options = self._pass_options(c, max_len=55.0)
        else:
            options = self._pass_options(c)
            gd = P.goal_distance(c.x, c.y, c.dir)
            if gd <= C.SHOT_RANGE and P.goal_angle(c.x, c.y, c.dir) > 0.12:
                x = P.xg(c.x, c.y, c.dir, pressure)
                if x >= C.SHOT_MIN_XG:
                    s = C.SHOT_WEIGHT * x + C.SHOT_BIAS + 0.1 * P.z(c.attrs["finishing"])
                    if x >= 0.25:
                        s += C.BIG_CHANCE_BOOST
                    options.append({"kind": "shot", "score": s, "xg": x})
            space = min((math.hypot(o.x - c.carry_tx, o.y - c.carry_ty) for o in opps), default=20.0)
            options.append({"kind": "carry", "score": C.CARRY_BASE + min(space, 10.0) / 10.0 - 1.2 * pressure})
            ahead = [o for o in opps if not o.is_gk and math.hypot(o.x - c.x, o.y - c.y) < 5.0
                     and (o.x - c.x) * c.dir > -1.0]
            if ahead:
                options.append({"kind": "dribble", "score": C.DRIBBLE_BASE + 0.25 * P.z(c.attrs["dribbling"])
                                - 0.4 * (len(ahead) - 1), "o": min(ahead, key=lambda o: math.hypot(o.x - c.x, o.y - c.y))})
            if R.advance(c.x, c.dir) < 30 and pressure > 0.4:
                options.append({"kind": "clear", "score": C.CLEAR_WEIGHT * pressure})
        if not options:
            options = [{"kind": "carry", "score": 0.0}]
        temp = P.decision_temperature(c.attrs["composure"])
        choice = options[P.softmax_choice(self.rng, [o["score"] for o in options], temp)]
        kind = choice["kind"]
        if kind == "pass":
            self._pass(c, choice)
        elif kind == "shot":
            self._shoot(c, kind="open", xg_value=choice["xg"])
        elif kind == "dribble":
            self._duel(choice["o"], c, carrier_initiated=True)
        elif kind == "clear":
            self._clear(c)
        else:
            c.carry_tx, c.carry_ty = self._carry_target(c)
            lo, hi = C.DECISION_INTERVAL
            self.next_decision = self.t + self.randint(lo, hi)

    # ------------------------------------------------------------------ passes
    def _pass(self, c: PlayerState, opt: dict) -> None:
        t = self.t
        m: PlayerState = opt["m"]
        ex, ey, d = opt["ex"], opt["ey"], opt["d"]
        lofted, cross = opt["lofted"], opt["cross"]
        defenders = self.on_pitch(1 - c.side)
        speed = C.LOFTED_SPEED if lofted else C.PASS_SPEED
        n = max(1, int(math.ceil(d / speed)))
        self.carrier = None
        self.last_touch_side = c.side
        # Offside at the moment of the pass.
        if R.is_offside(m.x, c.x, [o.x for o in defenders], c.dir) and self.rng.random() > C.OFFSIDE_ERROR_P:
            ev = self.emit("pass", c, other=m, frm=(c.x, c.y), to=(ex, ey), outcome="fail")
            self.last_pass = (c, m, t, ev)
            self.emit("offside", m, frm=(m.x, m.y), outcome="none")
            taker = min((o for o in defenders), key=lambda o: math.hypot(o.x - m.x, o.y - m.y))
            self._set_restart("free_kick", 1 - c.side, m.x, m.y, taker, wait=C.RESTART_WAIT["offside"])
            return
        roll = self.rng.random()
        result, winner = "complete", None
        if roll >= opt["pc"]:
            lane_def = opt["lane_def"]
            if lofted:
                contest = min(defenders, key=lambda o: math.hypot(o.x - ex, o.y - ey))
                if math.hypot(contest.x - ex, contest.y - ey) < C.AERIAL_CONTEST_M + 3.0:
                    result, winner = "aerial_lost", contest
                else:
                    result = "misplaced"
            elif lane_def is not None and self.rng.random() < C.PASS_INTERCEPT_SHARE:
                result, winner = "intercept", lane_def
                u = opt["lane_u"]
                ex, ey = c.x + (ex - c.x) * u, c.y + (ey - c.y) * u
                n = max(1, int(math.ceil(d * u / speed)))
            elif opt["marker"] is not None and not opt["marker"].is_gk and self.rng.random() < C.PASS_INTERCEPT_SHARE:
                result, winner = "intercept", opt["marker"]  # the marker steps in front of the receiver
            else:
                result = "misplaced"
        gk = self.keeper(1 - c.side)
        if result == "complete" and cross and math.hypot(gk.x - ex, gk.y - ey) < 9.0 and self.rng.random() < C.GK_CLAIM_P * 0.5:
            result, winner = "gk_claim", gk
        elif result == "complete" and not cross and R.in_attacking_box(ex, ey, c.dir):
            line = R.second_last_defender_x([o.x for o in defenders], c.dir)
            behind = (ex - line) * c.dir > 0
            if behind and math.hypot(gk.x - ex, gk.y - ey) < 0.9 * math.hypot(m.x - ex, m.y - ey) and self.rng.random() < C.GK_SWEEP_P:
                result, winner = "gk_sweep", gk
        if result == "misplaced":
            err = C.MISPLACED_ERROR[0] + C.MISPLACED_ERROR[1] * d
            ex, ey = ex + float(self.rng.normal(0, err)), ey + float(self.rng.normal(0, err))
            if ex < 0 or ex > C.PITCH_L or ey < 0 or ey > C.PITCH_W:
                result = "out"
                ex, ey = min(C.PITCH_L, max(0.0, ex)), min(C.PITCH_W, max(0.0, ey))
            else:
                result = "loose"
            n = max(1, int(math.ceil(math.hypot(ex - c.x, ey - c.y) / speed)))  # the ball travels to where it lands
        outcome = "success" if result == "complete" else "fail"
        ev = self.emit("pass", c, other=m, frm=(c.x, c.y), to=(ex, ey), outcome=outcome)
        self.last_pass = (c, m, t, ev)
        self.state = "flight"
        self.flight = Flight("pass", c.x, c.y, ex, ey, t, t + n, result, c.side, passer=c, receiver=m,
                             winner=winner, cross=cross, pass_event=ev)
        if result == "aerial_lost":
            self.flight.loser = m

    def _clear(self, c: PlayerState) -> None:
        t = self.t
        dist_m = self.uniform(30.0, 50.0)
        ang = float(self.rng.normal(0, 0.5))
        ex = c.x + math.cos(ang) * dist_m * c.dir
        ey = c.y + math.sin(ang) * dist_m
        result = "loose"
        if ex < 0 or ex > C.PITCH_L or ey < 0 or ey > C.PITCH_W:
            result = "out"
            ex, ey = min(C.PITCH_L, max(0.0, ex)), min(C.PITCH_W, max(0.0, ey))
        self.emit("clearance", c, frm=(c.x, c.y), to=(ex, ey), outcome="success")
        self.carrier = None
        self.last_touch_side = c.side
        self.last_pass = None
        self.state = "flight"
        self.flight = Flight("clear", c.x, c.y, ex, ey, t, t + max(1, int(math.ceil(dist_m / C.LOFTED_SPEED))),
                             result, c.side)

    def _resolve_flight(self) -> None:
        f = self.flight
        assert f is not None
        res = f.result
        if res == "complete":
            self._give_ball(f.receiver)
            if f.cross:
                defenders = self.on_pitch(1 - f.side)
                rival = min(defenders, key=lambda o: math.hypot(o.x - f.ex, o.y - f.ey))
                if math.hypot(rival.x - f.ex, rival.y - f.ey) < C.AERIAL_CONTEST_M and not rival.is_gk:
                    self.emit("aerial_duel", f.receiver, other=rival, frm=(f.ex, f.ey), outcome="success")
                self._decide(f.receiver, forced="header")
            elif f.kind == "pass" and f.pass_event and math.hypot(f.ex - f.sx, f.ey - f.sy) > C.LOFTED_DISTANCE:
                defenders = self.on_pitch(1 - f.side)
                rival = min(defenders, key=lambda o: math.hypot(o.x - f.ex, o.y - f.ey))
                if math.hypot(rival.x - f.ex, rival.y - f.ey) < C.AERIAL_CONTEST_M and not rival.is_gk:
                    self.emit("aerial_duel", f.receiver, other=rival, frm=(f.ex, f.ey), outcome="success")
        elif res == "intercept":
            ev = self.emit("interception", f.winner, other=f.passer, frm=(f.ex, f.ey), outcome="success")
            self._give_ball(f.winner, ev, f.passer.id if f.passer else None)
        elif res == "aerial_lost":
            ev = self.emit("aerial_duel", f.winner, other=f.loser, frm=(f.ex, f.ey), outcome="success")
            w = f.winner
            lx, ly = clamp_to_pitch(f.ex + w.dir * self.uniform(5, 10), f.ey + float(self.rng.normal(0, 4)), 1.0)
            self._set_loose(lx, ly)
            self.last_touch_side = w.side
            if R.advance(w.x, w.dir) < 35:
                self.emit("clearance", w, frm=(f.ex, f.ey), to=(lx, ly), outcome="success", related=[ev])
        elif res == "gk_claim":
            ev = self.emit("gk_claim", f.winner, other=f.receiver, frm=(f.ex, f.ey), outcome="success")
            self._give_ball(f.winner, ev, None)
            self.next_decision = self.t + self.randint(3, 6)
        elif res == "gk_sweep":
            ev = self.emit("gk_sweep", f.winner, other=f.receiver, frm=(f.ex, f.ey), outcome="success")
            self._give_ball(f.winner, ev, None)
        elif res == "loose":
            self._set_loose(f.ex, f.ey)
        elif res == "out":
            self._out_of_play(f.ex, f.ey)
        else:
            self._shot_followup(f)

    def _out_of_play(self, x: float, y: float) -> None:
        last_dir = 1 if self.last_touch_side == 0 else -1
        rtype, award_dir, (sx, sy) = R.out_of_play(x, y, last_dir)
        side = 0 if award_dir > 0 else 1
        self.state = "dead"
        self.carrier = None
        self.flight = None
        team = self.on_pitch(side)  # the ball is fetched to the spot at DEAD_BALL_SPEED, never teleported
        if rtype == "goal_kick":
            taker = self.keeper(side)
        elif rtype == "corner":
            pool = [p for p in R.set_piece_order(team) if p.position not in (Position.ST, Position.CB)]
            taker = pool[0] if pool else R.set_piece_order(team)[0]
        else:
            taker = min((p for p in team if not p.is_gk), key=lambda p: math.hypot(p.x - sx, p.y - sy))
        self._set_restart(rtype, side, sx, sy, taker)

    def _set_restart(self, rtype: str, side: int, sx: float, sy: float, taker: PlayerState, wait=None,
                     direct: bool = False, fouled: str | None = None, card: bool = False, extra: int = 0) -> None:
        lo, hi = wait or C.RESTART_WAIT[rtype]
        self.state = "dead"
        self.carrier = None
        self.flight = None
        self.restart = Restart(rtype, side, sx, sy, self.t + self.randint(lo, hi) + extra, taker, direct, fouled, card)
        self.next_decision = 10**9

    def _take_restart(self) -> None:
        r = self.restart
        assert r is not None
        taker = r.taker
        if not taker.on_pitch:
            taker = min((p for p in self.on_pitch(r.side) if not p.is_gk), key=lambda p: math.hypot(p.x - r.sx, p.y - r.sy))
        if r.type != "penalty":
            self.emit(r.type, taker, frm=(r.sx, r.sy), outcome="none")
        self.restart = None
        self._give_ball(taker, kind="restart")
        forced = {"kickoff": "kickoff", "throw_in": "throw_in", "goal_kick": "goal_kick", "corner": "corner",
                  "free_kick": "free_kick_direct" if r.direct else "free_kick", "penalty": "penalty"}[r.type]
        self._decide(taker, forced=forced)

    # ------------------------------------------------------------------ shots
    def _assister(self, shooter: PlayerState) -> tuple[PlayerState | None, Event | None]:
        lp = self.last_pass
        if lp and lp[1] is shooter and lp[3]["outcome"] == "success" and self.t - lp[2] <= 15 and lp[0].side == shooter.side:
            return lp[0], lp[3]
        return None, None

    def _shoot(self, c: PlayerState, kind: str, xg_value: float | None = None) -> None:
        t = self.t
        gk = self.keeper(1 - c.side)
        defenders = [o for o in self.on_pitch(1 - c.side) if not o.is_gk]
        pressure = self._pressure(c.x, c.y, c.side)
        gx = P.goal_x(c.dir)
        if kind == "penalty":
            x = C.PENALTY_XG
        elif kind == "free_kick":
            x = P.xg(c.x, c.y, c.dir, 0.0) * C.XG_FREE_KICK
        else:
            x = xg_value if xg_value is not None else P.xg(c.x, c.y, c.dir, pressure, header=kind == "header")
        if kind == "header":
            spd = min(C.SHOT_SPEED_KMH[2], max(25.0, float(self.rng.normal(*C.HEADER_SPEED_KMH))))
        else:
            mean, sd, cap = C.SHOT_SPEED_KMH
            spd = min(cap, max(45.0, float(self.rng.normal(mean + 2.5 * P.z(c.attrs["finishing"]), sd))))
        aim_y = C.PITCH_W / 2 + self.uniform(-C.GOAL_HALF_WIDTH + 0.3, C.GOAL_HALF_WIDTH - 0.3)
        assister, key_ev = self._assister(c)
        self.carrier = None
        self.last_touch_side = c.side
        fin, comp, ss = P.z(c.attrs["finishing"]), P.z(c.attrs["composure"]), P.z(gk.attrs.get("shot_stopping", 60))
        outcome, blocker = None, None
        if kind == "penalty":
            p_goal = min(0.92, max(0.6, 0.78 + 0.03 * P.z(c.attrs["set_pieces"]) + 0.02 * comp - 0.04 * ss))
            roll = self.rng.random()
            outcome = "goal" if roll < p_goal else ("saved" if roll < p_goal + (1 - p_goal) * 0.7 else "off_target")
        else:
            block_p = C.BLOCK_P_EACH * (0.7 if kind == "free_kick" else 1.0)
            for o in sorted(defenders, key=lambda o: o.id):
                dl, u = P.segment_distance(o.x, o.y, c.x, c.y, gx, aim_y)
                if 0.05 < u < 0.95 and dl < C.BLOCK_LINE_M and self.rng.random() < block_p:
                    outcome, blocker = "blocked", o
                    break
            if outcome is None:
                p_on = min(0.9, max(0.15, C.ON_TARGET_BASE + C.ON_TARGET_FIN * fin + C.ON_TARGET_XG * x))
                if self.rng.random() < p_on:
                    mult = math.exp(C.FIN_ODDS * fin + C.COMP_ODDS * comp - C.GK_ODDS * ss)
                    p_goal = min(0.97, max(0.02, C.GOAL_K * x * mult / p_on))
                    outcome = "goal" if self.rng.random() < p_goal else "saved"
                else:
                    outcome = "post" if (x > 0.05 and self.rng.random() < C.POST_SHARE) else "off_target"
        # Ball end point and follow-up.
        if outcome == "blocked":
            ex, ey = blocker.x, blocker.y
        elif outcome in ("goal", "saved"):
            ex, ey = (gx, aim_y) if outcome == "goal" else (gk.x, gk.y)
        elif outcome == "post":
            ex, ey = gx, C.PITCH_W / 2 + math.copysign(C.GOAL_HALF_WIDTH, aim_y - C.PITCH_W / 2)
        else:
            wide = C.GOAL_HALF_WIDTH + self.uniform(0.5, 6.0)
            ex, ey = gx, C.PITCH_W / 2 + math.copysign(wide, aim_y - C.PITCH_W / 2)
        if kind == "penalty":
            frm = (c.x, c.y)
        else:
            frm = (c.x, c.y)
        if key_ev is not None and key_ev["type"] == "pass":
            key_ev["type"] = "key_pass"
        if outcome == "goal":
            self.score[c.side] += 1
        shot_ev = self.emit("shot", c, other=gk if outcome in ("saved", "goal") else blocker, frm=frm, to=(ex, ey),
                            outcome=outcome, xg=x, speed_kmh=spd, related=[key_ev] if key_ev else [])
        shot_ev["_kind"] = kind
        if outcome == "blocked":
            if self.rng.random() < C.HANDBALL_P:
                shot_ev["outcome"] = "blocked"
                self._handball(blocker, c)
                return
            self.emit("block", blocker, other=c, frm=(blocker.x, blocker.y), outcome="success", related=[shot_ev])
        elif outcome == "saved":
            self.emit("save", gk, other=c, frm=(gk.x, gk.y), outcome="success", xg=x, related=[shot_ev])
        elif outcome == "goal":
            self.emit("goal", c, other=assister, frm=frm, to=(ex, ey), outcome="goal", xg=x,
                      related=[shot_ev] + ([key_ev] if key_ev else []))
        travel = math.hypot(ex - c.x, ey - c.y)
        n = max(1, int(math.ceil(travel / min(29.5, spd / 3.6))))
        self.state = "flight"
        self.flight = Flight("shot", c.x, c.y, ex, ey, t, t + n, f"shot_{outcome}", c.side, passer=c, winner=gk,
                             loser=blocker)

    def _shot_followup(self, f: Flight) -> None:
        res = f.result
        shooter = f.passer
        gk = self.keeper(1 - f.side)
        if res == "shot_goal":
            self._goal_celebration(shooter)
            return
        if res == "shot_saved":
            roll = self.rng.random()
            if roll < C.SAVE_HOLD:
                self._give_ball(gk)
                self.next_decision = self.t + self.randint(4, 8)
            elif roll < C.SAVE_HOLD + C.SAVE_CORNER:
                self.last_touch_side = gk.side
                self._out_of_play(P.goal_x(shooter.dir), C.PITCH_W / 2 + (-12.0 if f.ey < C.PITCH_W / 2 else 12.0))
            else:
                lx = P.goal_x(shooter.dir) - shooter.dir * self.uniform(6, 11)
                self._set_loose(lx, C.PITCH_W / 2 + float(self.rng.normal(0, 6)))
            return
        if res == "shot_blocked":
            if self.rng.random() < 0.4 and f.loser is not None:
                self.last_touch_side = f.loser.side
                self._out_of_play(P.goal_x(shooter.dir), C.PITCH_W / 2 + (-12.0 if f.ey < C.PITCH_W / 2 else 12.0))
            else:
                b = f.loser or shooter
                self._set_loose(*clamp_to_pitch(b.x - shooter.dir * self.uniform(2, 6), b.y + float(self.rng.normal(0, 3)), 1.0))
            return
        if res == "shot_post" and self.rng.random() < 0.5:
            lx = P.goal_x(shooter.dir) - shooter.dir * self.uniform(4, 9)
            self._set_loose(lx, C.PITCH_W / 2 + float(self.rng.normal(0, 5)))
            return
        self.last_touch_side = shooter.side
        self._out_of_play(P.goal_x(shooter.dir), f.ey)

    def _goal_celebration(self, scorer: PlayerState) -> None:
        t = self.t
        flag_y = 2.0 if scorer.y < C.PITCH_W / 2 else C.PITCH_W - 2.0
        flag_x = P.goal_x(scorer.dir) - scorer.dir * 2.0
        scorer.override, scorer.override_until, scorer.override_target = "celebrate", t + C.CELEBRATION_S, (flag_x, flag_y)
        mates = sorted((p for p in self.on_pitch(scorer.side) if p is not scorer and not p.is_gk),
                       key=lambda p: (math.hypot(p.x - scorer.x, p.y - scorer.y), p.id))
        for p in mates[: self.randint(3, 5)]:
            p.override, p.override_until, p.override_target = "huddle", t + C.CELEBRATION_S, scorer
        place_ball(self.ball, self.flight.ex if self.flight else self.ball.x, self.flight.ey if self.flight else self.ball.y)
        self.celebration = {"side": scorer.side, "until": t + C.CELEBRATION_S}
        conceding = 1 - scorer.side
        self._set_restart("kickoff", conceding, C.PITCH_L / 2, C.PITCH_W / 2, self._kicker(conceding))

    # ------------------------------------------------------------------ duels and fouls
    def _duel(self, o: PlayerState, c: PlayerState, carrier_initiated: bool = False) -> None:
        """A defender within reach of the carrier: foul, dribble beaten, or tackle won."""
        foul_p = C.FOUL_P * C.FOUL_TEMPERAMENT[o.temperament]
        foul_p *= 1.0 + C.FOUL_PRESS * (float(self.tac(o.side, "press_intensity")) - 0.5)
        foul_p *= 1.0 - 0.3 * (o.attrs["defending"] - 60) / 40.0
        if o.yellows and o.temperament != "hot-headed":
            foul_p *= C.FOUL_ON_YELLOW
        if R.in_own_penalty_area(c.x, c.y, o.dir):
            foul_p *= C.FOUL_IN_OWN_BOX
        if self.rng.random() < foul_p:
            self._foul(o, c)
            return
        keep = P.logistic(C.DUEL_BASE + C.DUEL_SKILL * (P.z(c.attrs["dribbling"]) - P.z(o.attrs["defending"]))
                          + C.DUEL_PACE * (P.z(c.attrs["pace"]) - P.z(o.attrs["pace"])))
        if self.rng.random() < keep:
            self.emit("dribble", c, other=o, frm=(c.x, c.y), outcome="success")
            o.beaten_until = self.t + C.BEATEN_COOLDOWN_S
            c.carry_tx, c.carry_ty = self._carry_target(c)
            self.next_decision = self.t + self.randint(1, 3)
        else:
            ev = self.emit("tackle", o, other=c, frm=(c.x, c.y), outcome="success")
            if self.rng.random() < C.TACKLE_KEEPS_BALL:
                self._give_ball(o, ev, c.id)
            else:
                self.last_touch_side = o.side
                ang = self.uniform(0, 2 * math.pi)
                self._set_loose(*clamp_to_pitch(c.x + 4 * math.cos(ang), c.y + 4 * math.sin(ang), 1.0))
                self.possessions.append((self.t, o.side, ev, c.id, "open"))
                self.poss_side = o.side

    def _is_last_defender(self, o: PlayerState, c: PlayerState) -> bool:
        ahead = [p for p in self.on_pitch(o.side) if not p.is_gk and p is not o
                 and (R.advance(p.x, c.dir) > R.advance(c.x, c.dir))]
        return not ahead

    def _foul(self, o: PlayerState, c: PlayerState) -> None:
        t = self.t
        harsh = self.rng.random() < C.REF_ERROR_P
        foul_ev = self.emit("foul", o, other=c, frm=(c.x, c.y), outcome="success")
        in_box = R.in_own_penalty_area(c.x, c.y, o.dir)
        cards: list[str] = []
        dogso = (not in_box and self._is_last_defender(o, c) and P.goal_distance(c.x, c.y, c.dir) < C.DOGSO_RANGE
                 and self.rng.random() < C.DOGSO_P)
        if dogso or self.rng.random() < C.RED_P:
            cards.append("red")
        elif self.rng.random() < C.YELLOW_P + (C.YELLOW_HOT if o.temperament == "hot-headed" else 0.0):
            cards.append("yellow")
        elif o.temperament == "hot-headed" and self.rng.random() < C.DISSENT_P:
            cards.append("yellow")
        for card in cards:
            if card == "yellow":
                o.yellows += 1
                self.emit("card_yellow", o, frm=(o.x, o.y), outcome="none", related=[foul_ev])
                if o.yellows >= 2:
                    self.emit("card_red", o, frm=(o.x, o.y), outcome="none", related=[foul_ev])
                    self._send_off(o)
            else:
                self.emit("card_red", o, frm=(o.x, o.y), outcome="none", related=[foul_ev])
                self._send_off(o)
        if self.rng.random() < C.INJURY_P:
            self.emit("injury", c, frm=(c.x, c.y), outcome="none", related=[foul_ev])
            c.override, c.override_until, c.override_target = "down", t + self.randint(*C.INJURY_DOWN_S), (c.x, c.y)
            helpers = sorted((p for p in self.players if p.on_pitch and p is not c and not p.is_gk),
                             key=lambda p: (math.hypot(p.x - c.x, p.y - c.y), p.id))
            for p in helpers[: self.randint(2, 3)]:
                p.override, p.override_until, p.override_target = "huddle", c.override_until, c
        if o.on_pitch and cards:
            o.override, o.override_until, o.override_target = "talk_ref", t + 5, self.ref
        if harsh or "red" in cards:
            mates = sorted((p for p in self.on_pitch(o.side) if p is not o and not p.is_gk),
                           key=lambda p: (math.hypot(p.x - o.x, p.y - o.y), p.id))
            for p in mates[: self.randint(1, 3)]:
                p.override, p.override_until, p.override_target = "talk_ref", t + self.randint(4, 7), self.ref
        extra = self.randint(*C.CARD_EXTRA_WAIT) if cards else 0
        self._award_free_kick(c, o, in_box, extra, bool(cards))

    def _award_free_kick(self, fouled: PlayerState, offender: PlayerState, in_box: bool, extra: int, card: bool) -> None:
        side = fouled.side
        team = self.on_pitch(side)
        if in_box:
            taker = R.set_piece_taker(team, exclude=fouled.id)
            spot_x = P.goal_x(fouled.dir) - fouled.dir * C.PENALTY_SPOT
            self.emit("penalty", taker, frm=(spot_x, C.PITCH_W / 2), outcome="awarded")
            self._set_restart("penalty", side, spot_x, C.PITCH_W / 2, taker, fouled=fouled.id, card=card, extra=extra)
            return
        sx, sy = fouled.x, fouled.y
        direct = (P.goal_distance(sx, sy, fouled.dir) <= C.FK_DIRECT_RANGE and P.goal_angle(sx, sy, fouled.dir) > 0.2
                  and self.rng.random() < C.FK_DIRECT_P)
        if direct:
            taker = R.set_piece_taker(team, exclude=fouled.id)
        else:
            taker = min((p for p in team if p is not fouled and not p.is_gk), key=lambda p: math.hypot(p.x - sx, p.y - sy))
        self._set_restart("free_kick", side, sx, sy, taker, direct=direct, fouled=fouled.id, card=card, extra=extra)

    def _handball(self, offender: PlayerState, victim: PlayerState) -> None:
        self.emit("handball", offender, frm=(offender.x, offender.y), outcome="none")
        in_box = R.in_own_penalty_area(offender.x, offender.y, offender.dir)
        self.flight = None
        self._award_free_kick(victim, offender, in_box, 0, False)

    def _send_off(self, o: PlayerState) -> None:
        o.on_pitch = False
        o.override, o.override_until = "sent_off", 10**9
        o.override_target = (C.PITCH_L / 2 + (-C.SENT_OFF_X_OFFSET if o.side == 0 else C.SENT_OFF_X_OFFSET), C.SENT_OFF_Y)
        self.sent_off[o.id] = self.t
        if o.number in (2, 3, 4, 5):  # the formation drops a midfield slot to fill the back line
            cover = next((p for p in self.sides[o.side] if p.on_pitch and p.number == 6), None)
            if cover is not None:
                cover.slot_xy = o.slot_xy

    # ------------------------------------------------------------------ (2) targets
    def _shape_target(self, p: PlayerState, bx: float, by: float, in_poss: bool) -> tuple[float, float]:
        sx, sy = p.slot_xy
        line = float(self.tac(p.side, "def_line"))
        width = float(self.tac(p.side, "width"))
        bdepth = R.advance(bx, p.dir)
        by_team = by if p.side == 0 else C.PITCH_W - by
        if p.is_gk:
            d_goal = math.hypot(bdepth, by_team - C.PITCH_W / 2)
            depth = min(C.GK_MAX_OFF_LINE, 1.5 + 0.12 * d_goal)
            y = C.PITCH_W / 2 + max(-4.5, min(4.5, (by_team - C.PITCH_W / 2) * C.GK_Y_FOLLOW))
            return self._team_point(p.side, depth, y)
        if in_poss:
            shift = C.PUSH_UP_BASE + C.PUSH_UP_LINE * line
            a, b = C.WIDTH_IN_POSSESSION
        else:
            shift = -(C.DROP_BASE + C.DROP_LINE * (1.0 - line))
            a, b = C.WIDTH_OUT_OF_POSSESSION
        depth = sx * C.PITCH_L + shift
        center = 0.42 * C.PITCH_L + shift
        depth += C.BALL_SHIFT_X * (bdepth - center)
        y = C.PITCH_W / 2 + (sy * C.PITCH_W - C.PITCH_W / 2) * (a + b * width) + C.BALL_SHIFT_Y * (by_team - C.PITCH_W / 2)
        x, yy = self._team_point(p.side, depth, y)
        return clamp_to_pitch(x, yy, 1.0)

    def _offside_limit(self, side: int) -> float:
        """Furthest x (in side's attacking direction) an attacker may stand without being offside."""
        d = 1 if side == 0 else -1
        line = R.second_last_defender_x([o.x for o in self.on_pitch(1 - side)], d)
        bx = self._ball_point()[0]
        limit = max(line, bx, C.PITCH_L / 2) if d > 0 else min(line, bx, C.PITCH_L / 2)
        return limit - d * C.OFFSIDE_LINE_MARGIN

    def _pick_targets(self) -> None:
        t = self.t
        bx, by = self._ball_point()
        for p in self.players:
            if p.override and t >= p.override_until:
                p.override, p.override_target = None, None
        if self.state == "dead":
            self._dead_targets(bx, by)
        else:
            self._open_play_targets(bx, by)
        for p in self.players:  # reactions override everything
            if p.override:
                tgt = p.override_target
                if isinstance(tgt, Body):
                    off = 1.5 if p.override in ("talk_ref", "huddle") else 0.0
                    p.tx, p.ty = clamp_to_pitch(tgt.x + off, tgt.y + (0.8 if p.id < tgt.id else -0.8))
                elif tgt is not None:
                    p.tx, p.ty = tgt
                p.intent = p.override

    def _open_play_targets(self, bx: float, by: float) -> None:
        t = self.t
        att = self.poss_side
        carrier = self.carrier if self.state == "carried" else None
        for p in self.players:
            if p.on_pitch:
                p.shape_x, p.shape_y = self._shape_target(p, bx, by, p.side == att)
                p.tx, p.ty, p.intent = p.shape_x, p.shape_y, "hold_shape"
        # Defending team
        dside = 1 - att
        defenders = [p for p in self.on_pitch(dside) if not p.is_gk]
        pressers: list[PlayerState] = []
        if carrier is not None:
            pi = float(self.tac(dside, "press_intensity"))
            trigger = C.PRESS_TRIGGER_BASE + C.PRESS_TRIGGER_K * pi
            pmax = C.PRESS_MAX_S["high" if pi >= 0.6 else "low"]
            ranked = sorted(defenders, key=lambda p: (math.hypot(p.x - carrier.x, p.y - carrier.y), p.id))
            danger = R.advance(carrier.x, 1 if att == 0 else -1) > C.PITCH_L - C.DANGER_ZONE_M
            for i, p in enumerate(ranked[:2]):
                d = math.hypot(p.x - carrier.x, p.y - carrier.y)
                if danger:  # near our goal the two nearest always close the carrier down
                    if d > C.DANGER_PRESS_M or t < p.beaten_until:
                        continue
                else:
                    limit = trigger if i == 0 else trigger * C.SECOND_PRESSER_RANGE
                    if i == 1 and pi < C.SECOND_PRESSER_MIN_INTENSITY:
                        break
                    if d > limit or t < p.press_cool_until or t < p.beaten_until:
                        continue
                    if math.hypot(carrier.x - p.shape_x, carrier.y - p.shape_y) > C.PRESS_MAX_FROM_SHAPE:
                        continue
                    if p.press_since < 0:
                        p.press_since = t
                    elif t - p.press_since > pmax:
                        p.press_since, p.press_cool_until = -1, t + C.PRESS_COOLDOWN_S
                        continue
                pressers.append(p)
                p.tx, p.ty = clamp_to_pitch(carrier.x + carrier.vx, carrier.y + carrier.vy)
                p.intent = "press"
        for p in defenders:
            if p not in pressers:
                p.press_since = -1
        loose_chasers: set[str] = set()
        if self.state == "loose":
            for side in (0, 1):
                cands = [p for p in self.on_pitch(side) if not p.is_gk and not p.override]
                if cands:
                    ch = min(cands, key=lambda p: (math.hypot(p.x - bx, p.y - by), p.id))
                    ch.tx, ch.ty, ch.intent = bx, by, "press" if side == dside else "make_run"
                    loose_chasers.add(ch.id)
        ball_depth_att = R.advance(bx, 1 if dside == 0 else -1)
        marked: set[str] = set()
        attackers = [o for o in self.on_pitch(att) if not o.is_gk and o is not carrier]
        flight_now = self.flight if self.state == "flight" else None
        for p in defenders:
            if p in pressers or p.id in loose_chasers:
                continue
            if flight_now is not None and flight_now.winner is p:
                p.tx, p.ty, p.intent = flight_now.ex, flight_now.ey, "press"
                continue
            ahead_of_ball = R.advance(p.x, p.dir) - ball_depth_att > 5.0
            if ahead_of_ball and math.hypot(p.x - p.shape_x, p.y - p.shape_y) > C.RECOVERY_DISTANCE_M:
                p.intent = "track_back"
                continue
            best, bd = None, C.MARK_ZONE_M
            for o in attackers:
                if o.id in marked:
                    continue
                d = math.hypot(o.x - p.shape_x, o.y - p.shape_y)
                if d < bd:
                    best, bd = o, d
            if best is not None:
                marked.add(best.id)
                gx = R.own_goal_x(p.dir)
                vx, vy = gx - best.x, C.PITCH_W / 2 - best.y
                n = math.hypot(vx, vy) or 1.0
                p.tx, p.ty = clamp_to_pitch(best.x + vx / n * C.MARK_OFFSET_M, best.y + vy / n * C.MARK_OFFSET_M, 0.5)
                p.intent = "mark"
        # Attacking team
        flight = self.flight if self.state == "flight" else None
        limit = self._offside_limit(att)
        adir = 1 if att == 0 else -1
        for p in self.on_pitch(att):
            if p.is_gk or p.id in loose_chasers:
                continue
            if p is carrier:
                p.tx, p.ty, p.intent = p.carry_tx, p.carry_ty, "carry"
                continue
            if flight is not None and flight.receiver is p and flight.result in ("complete", "aerial_lost", "intercept", "gk_claim", "gk_sweep"):
                p.tx, p.ty, p.intent = flight.ex, flight.ey, "make_run"
                continue
            if p.run_until >= t:
                p.tx, p.ty, p.intent = p.run_tx, p.run_ty, "make_run"
                continue
            role = RUNNER_POSITIONS.get(p.position, 0.0)
            if role and carrier is not None and self.rng.random() < C.RUN_START_P * role * (0.5 + p.attrs["work_rate"] / 99.0):
                fwd = self.uniform(*C.RUN_FORWARD_M)
                rx = p.shape_x + adir * fwd
                ry = p.shape_y + float(self.rng.normal(0, 4))
                if self.rng.random() < C.RUN_RESPECTS_OFFSIDE_P:
                    rx = min(rx, limit) if adir > 0 else max(rx, limit)
                p.run_tx, p.run_ty = clamp_to_pitch(rx, ry, 1.0)
                p.run_until = t + self.randint(*C.RUN_LENGTH_S)
                p.tx, p.ty, p.intent = p.run_tx, p.run_ty, "make_run"
                continue
            tx = min(p.shape_x, limit) if adir > 0 else max(p.shape_x, limit)
            p.tx, p.ty = tx, p.shape_y
            if carrier is not None and p.position in SUPPORT_POSITIONS:
                sx = p.tx + 0.25 * (carrier.x - p.tx)
                sy = p.ty + 0.25 * (carrier.y - p.ty)
                if math.hypot(sx - carrier.x, sy - carrier.y) > 8.0:
                    p.tx, p.ty = sx, sy
        for side in (0, 1):
            gk = self.keeper(side)
            if gk.on_pitch and gk is not carrier:
                gk.tx, gk.ty, gk.intent = gk.shape_x, gk.shape_y, "keeper"

    def _dead_targets(self, bx: float, by: float) -> None:
        r = self.restart
        if r is None:
            return
        t = self.t
        celebrating = self.celebration and t < self.celebration["until"]
        for p in self.players:
            if not p.on_pitch:
                continue
            if r.type == "kickoff":
                p.tx, p.ty = self._kickoff_xy(p, r.side)
                p.intent = "reset"
                if celebrating and p.side != self.celebration["side"]:
                    p.intent = "reset"
                p.shape_x, p.shape_y = p.tx, p.ty
                continue
            p.shape_x, p.shape_y = self._shape_target(p, r.sx, r.sy, p.side == r.side)
            p.tx, p.ty, p.intent = p.shape_x, p.shape_y, "reset"
        if r.type == "kickoff":
            return
        att, dfn = self.on_pitch(r.side), self.on_pitch(1 - r.side)
        adir = 1 if r.side == 0 else -1
        gx_att = P.goal_x(adir)
        if r.type == "penalty":
            for p in self.players:
                if not p.on_pitch:
                    continue
                if p.is_gk and p.side != r.side:
                    p.tx, p.ty, p.intent = gx_att, C.PITCH_W / 2, "keeper"
                elif p is not r.taker and not (p.is_gk):
                    edge = gx_att - adir * (C.BOX_DEPTH + 2.0)
                    p.tx = edge - adir * (abs(hash_offset(p.id)) % 6)
                    p.ty = C.PITCH_W / 2 + (hash_offset(p.id) % 30) - 15
                    p.intent = "set_piece_wait"
        elif r.type == "corner" or (r.type == "free_kick" and R.advance(r.sx, adir) > 70 and not r.direct):
            box_x = gx_att - adir * 9.0
            runners = [p for p in att if p.position in (Position.CB, Position.ST, Position.AM, Position.W) and p is not r.taker]
            for i, p in enumerate(runners[:5]):
                p.tx, p.ty, p.intent = box_x - adir * (i % 3) * 2.5, C.PITCH_W / 2 - 8 + i * 4.0, "set_piece_wait"
            markers = [p for p in dfn if not p.is_gk]
            for p, o in zip(markers, runners[:5]):
                p.tx, p.ty, p.intent = o.tx + adir * 1.5, o.ty, "mark"
            gk = self.keeper(1 - r.side)
            gk.tx, gk.ty, gk.intent = gx_att - adir * 1.0, C.PITCH_W / 2, "keeper"
        elif r.type == "free_kick" and r.direct:
            vx, vy = gx_att - r.sx, C.PITCH_W / 2 - r.sy
            n = math.hypot(vx, vy) or 1.0
            wx, wy = r.sx + vx / n * C.CENTER_CIRCLE_R, r.sy + vy / n * C.CENTER_CIRCLE_R
            wall = sorted((p for p in dfn if not p.is_gk), key=lambda p: (math.hypot(p.x - wx, p.y - wy), p.id))[:3]
            for i, p in enumerate(wall):
                p.tx, p.ty, p.intent = wx - vy / n * (i - 1) * 0.8, wy + vx / n * (i - 1) * 0.8, "wall"
            gk = self.keeper(1 - r.side)
            gk.tx, gk.ty, gk.intent = gx_att - adir * 1.0, C.PITCH_W / 2 + (r.sy - C.PITCH_W / 2) * 0.1, "keeper"
        # Opponents keep 9.15 m from the ball at free kicks and corners (except the wall and markers set above).
        if r.type in ("free_kick", "corner"):
            for p in dfn:
                if p.intent in ("wall", "keeper", "mark"):
                    continue
                d = math.hypot(p.tx - r.sx, p.ty - r.sy)
                if d < C.CENTER_CIRCLE_R:
                    vx, vy = (p.tx - r.sx, p.ty - r.sy) if d > 0.1 else (-adir, 0.0)
                    n = math.hypot(vx, vy)
                    p.tx, p.ty = clamp_to_pitch(r.sx + vx / n * C.CENTER_CIRCLE_R, r.sy + vy / n * C.CENTER_CIRCLE_R, 0.5)
        tk = r.taker
        if tk.on_pitch:
            tk.tx, tk.ty, tk.intent = r.sx, r.sy, "take_set_piece"
            if r.type == "penalty":
                tk.tx = r.sx - adir * 1.0

    def _speed_cap(self, p: PlayerState) -> float:
        """Intent speed, scaled up for a high-press team (they run more off the ball)."""
        cap = self._intent_speed(p)
        if p.intent in ("hold_shape", "mark", "support", "press", "track_back", "make_run"):
            base, k = C.TEAM_WORK_SPEED
            cap *= base + k * float(self.tac(p.side, "press_intensity"))
        return cap

    def _intent_speed(self, p: PlayerState) -> float:
        intent = p.intent
        if intent in ("hold_shape", "reset", "keeper"):
            d = math.hypot(p.tx - p.x, p.ty - p.y)
            if d < C.SLOW_NEAR_TARGET_M:
                return C.WALK_SPEED
            if d > 15.0 and intent == "hold_shape":
                return C.CATCH_UP_SPEED
            return C.INTENT_SPEED[intent]
        return C.INTENT_SPEED.get(intent, 4.0)

    # ------------------------------------------------------------------ (5) activities
    def _activity(self, p: PlayerState, speed: float) -> str:
        if not p.on_pitch:
            return "sent_off"
        intent = p.intent
        if intent in OVERRIDE_ACTIVITIES:
            return intent
        if intent in MOVING_ACTIVITIES:
            return intent if speed >= C.ACT_WALK else speed_label(speed)
        if intent == "mark":
            return "mark" if speed < C.ACT_RUN else speed_label(speed)
        if intent == "hold_shape" and speed < C.ACT_WALK and math.hypot(p.tx - p.x, p.ty - p.y) < 3.0:
            return "hold_shape"
        return speed_label(speed)

    # ------------------------------------------------------------------ (6) referee and ball
    def _move_ref_and_ball(self) -> None:
        bx, by = self._ball_point() if self.state == "dead" else (self.ball.x, self.ball.y)
        vx, vy = C.PITCH_L / 2 - bx, C.PITCH_W / 2 - by
        n = math.hypot(vx, vy)
        if n < 1.0:
            vx, vy, n = 0.0, 1.0, 1.0
        move_player(self.ref, bx + vx / n * C.REF_OFFSET_M, by + vy / n * C.REF_OFFSET_M, C.REF_SPEED)
        if self.state == "carried" and self.carrier is not None:
            c = self.carrier
            sp = c.speed
            ux, uy = (c.vx / sp, c.vy / sp) if sp > 0.1 else (float(c.dir), 0.0)
            place_ball(self.ball, c.x + 0.5 * ux, c.y + 0.5 * uy)
        elif self.state == "flight" and self.flight is not None:
            f = self.flight
            frac = min(1.0, (self.t - f.depart) / max(1, f.arrive - f.depart))
            place_ball(self.ball, f.sx + (f.ex - f.sx) * frac, f.sy + (f.ey - f.sy) * frac)
        elif self.state == "dead" and self.restart is not None:
            hold = self.celebration and self.t < self.celebration["until"] and self.restart.type == "kickoff"
            if not hold:
                move_ball_toward(self.ball, self.restart.sx, self.restart.sy, C.DEAD_BALL_SPEED)


def hash_offset(pid: str) -> int:
    """Small deterministic per-player offset for set-piece layouts (no RNG, no Python hash())."""
    return sum((i + 1) * ord(ch) for i, ch in enumerate(pid))


def simulate(world: World, seed: int) -> MatchResult:
    """Run one full match."""
    return Match(world, seed).run()
