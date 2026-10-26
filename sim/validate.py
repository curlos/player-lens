"""Match-file validation (specs/match-files.md, "Validation"). Run before writing; any problem aborts.

Two layers: the JSON schemas in contracts/ (shape) and the cross-file checks below (meaning).
"""

from __future__ import annotations

import json
import math
from collections import defaultdict
from pathlib import Path

import jsonschema

from sim import config as C
from sim.models import EventsFile, Meta, PositionsFile, RatingsFile
from sim.movement import player_speed

ROOT = Path(__file__).resolve().parent.parent
CONTRACTS = ROOT / "contracts"
SCHEMA_FOR = {"meta.json": "meta.schema.json", "events.json": "events.schema.json",
              "ratings.json": "ratings.schema.json", "positions.json": "positions.schema.json"}
SPEED_TOLERANCE = 0.15  # m/s: positions are rounded to decimeters
BALL_SPEED_CAP = 30.0
BALL_MARGIN_DM = 10


def schema_problems(texts: dict[str, str]) -> list[str]:
    """Validate each file's JSON against its contract."""
    problems = []
    for name, schema_file in SCHEMA_FOR.items():
        schema = json.loads((CONTRACTS / schema_file).read_text(encoding="utf-8"))
        try:
            jsonschema.validate(json.loads(texts[name]), schema)
        except jsonschema.ValidationError as exc:
            problems.append(f"{name}: schema: {exc.message}")
    return problems


def match_problems(meta: Meta, events: EventsFile, ratings: RatingsFile, positions: PositionsFile) -> list[str]:
    """Every cross-file check from specs/match-files.md. Returns a list of problems (empty = valid)."""
    p: list[str] = []
    ids_by_file = {"meta": meta.match_id, "events": events.match_id, "ratings": ratings.match_id,
                   "positions": positions.match_id}
    if len(set(ids_by_file.values())) != 1:
        p.append(f"files belong to different matches: {ids_by_file}")
    roster = {pl.id: pl for team in meta.teams for pl in team.players}
    ev = events.events
    # Events: unique ids, time order, range, references.
    ids = [e.id for e in ev]
    if len(set(ids)) != len(ids):
        p.append("event ids are not unique")
    if ids != [f"e_{i + 1:04d}" for i in range(len(ids))]:
        p.append("event ids are not e_0001 upward")
    if any(b.t < a.t for a, b in zip(ev, ev[1:])):
        p.append("events are not in time order")
    id_set = set(ids)
    for e in ev:
        if not 0 <= e.t <= meta.duration_s:
            p.append(f"{e.id}: t {e.t} outside the match")
        if e.player not in roster or (e.other and e.other not in roster):
            p.append(f"{e.id}: unknown player reference")
        if e.player[:3] != e.team and e.type not in ("error_leading_to_goal",):
            p.append(f"{e.id}: player {e.player} is not on team {e.team}")
        for r in e.related or []:
            if r not in id_set:
                p.append(f"{e.id}: related {r} does not exist")
    goals = [e for e in ev if e.type == "goal"]
    final = ev[-1].score if ev else None
    if final is None or final.model_dump() != meta.score.model_dump():
        p.append("final event score does not equal meta.score")
    if len(goals) != meta.score.azc + meta.score.rdm:
        p.append("number of goal events does not equal the total score")
    if any(sum(g.team == t for g in goals) != getattr(meta.score, t) for t in ("azc", "rdm")):
        p.append("goal events per team do not match the score")
    # Ratings: references, sums, soft-cap arithmetic.
    running: dict[str, float] = defaultdict(lambda: ratings.start)
    last_t = -1.0
    for r in ratings.entries:
        if r.event_id not in id_set:
            p.append(f"{r.id}: event {r.event_id} does not exist")
        if r.player not in roster:
            p.append(f"{r.id}: unknown player {r.player}")
        if r.t < last_t:
            p.append(f"{r.id}: rating entries are not in time order")
        last_t = r.t
        if abs(r.delta - r.raw_delta * r.scale) > 0.01:
            p.append(f"{r.id}: delta {r.delta} != raw_delta x scale")
        running[r.player] += r.delta
        if abs(running[r.player] - r.rating_after) > 0.01:
            p.append(f"{r.id}: rating_after {r.rating_after} != 6.0 + sum of deltas {running[r.player]:.2f}")
    # Positions: entities, lengths, bounds, speed.
    if positions.seconds != math.floor(meta.duration_s) + 1:
        p.append("positions.seconds must be floor(duration_s) + 1")
    if [e.id for e in positions.entities] != meta.entity_order or len(meta.entity_order) != 24:
        p.append("positions entities must follow meta.entity_order (24 entities)")
    L, W = int(C.PITCH_L * 10), int(C.PITCH_W * 10)
    for ent in positions.entities:
        xy = ent.xy
        if len(xy) != 2 * positions.seconds:
            p.append(f"{ent.id}: xy length {len(xy)} != 2 x seconds")
            continue
        is_ball = ent.id == "ball"
        if (ent.act is None) != is_ball or (ent.act is not None and len(ent.act) != positions.seconds):
            p.append(f"{ent.id}: act must exist (one per second) for players and the referee only")
        if ent.act is not None and any(not 0 <= a < len(meta.activities) for a in ent.act):
            p.append(f"{ent.id}: activity index outside meta.activities")
        margin = BALL_MARGIN_DM if is_ball else 0
        xs, ys = xy[0::2], xy[1::2]
        if min(xs) < -margin or max(xs) > L + margin or min(ys) < -margin or max(ys) > W + margin:
            p.append(f"{ent.id}: leaves the pitch")
        if is_ball:
            cap = BALL_SPEED_CAP
        elif ent.id == "ref":
            cap = C.REF_SPEED
        else:
            cap = player_speed(roster[ent.id].attributes.pace)
        cap = cap + SPEED_TOLERANCE
        fastest = max(math.hypot(xs[i] - xs[i - 1], ys[i] - ys[i - 1]) for i in range(1, len(xs))) / 10.0
        if fastest > cap:
            p.append(f"{ent.id}: moved {fastest:.2f} m in one second (cap {cap:.2f})")
    return p
