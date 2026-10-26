"""Build the four match files from one seed: simulate, derive off-ball events, rate, score importance.

Steps: simulator -> off-ball detection (rating/offball.py) -> shape checks -> time-ordered ids and running
score -> rating log (rating/engine.py) -> event importance -> Pydantic models (specs/match-files.md).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from rating import engine as RE
from rating import offball
from sim import config as C
from sim.engine import ACTIVITIES, MatchResult, simulate
from sim.models import (
    SCHEMA_VERSION,
    EntityTrack,
    Event,
    EventsFile,
    MatchPlayer,
    MatchTeam,
    Meta,
    PositionsFile,
    RatingEntry,
    RatingsFile,
    World,
)


@dataclass(frozen=True)
class MatchInfo:
    """Library entry: how a match is labelled. The seed decides everything else."""

    match_id: str
    seed: int
    label: str
    matchday: int
    blurb: str | None = None
    hero: bool = False
    title_decider: bool = False
    default_player: str = "azc_09"


@dataclass
class MatchFiles:
    meta: Meta
    events: EventsFile
    ratings: RatingsFile
    positions: PositionsFile
    result: MatchResult

    def texts(self) -> dict[str, str]:
        """Canonical JSON text per file name (byte-identical for the same seed)."""
        return {
            "meta.json": json.dumps(self.meta.model_dump(mode="json", exclude_none=True), indent=2, ensure_ascii=False) + "\n",
            "events.json": _lines(self.events.model_dump(mode="json", by_alias=True, exclude_none=True), "events"),
            "ratings.json": _lines(self.ratings.model_dump(mode="json", exclude_none=True), "entries"),
            "positions.json": json.dumps(self.positions.model_dump(mode="json", exclude_none=True),
                                         separators=(",", ":")) + "\n",
        }


def _lines(doc: dict, key: str) -> str:
    """JSON with one list item per line: compact, but diff-friendly."""
    items = doc.pop(key)
    head = json.dumps(doc, ensure_ascii=False)[:-1]
    body = ",\n".join("  " + json.dumps(i, ensure_ascii=False, separators=(", ", ": ")) for i in items)
    return f'{head}, "{key}": [\n{body}\n]}}\n'


def _sort_key(ev: dict) -> tuple:
    return (ev["t"], ev.get("_phase", 0), ev["_seq"])


def assemble_events(r: MatchResult) -> list[dict]:
    """All events (simulator + derived + shape checks) in time order with ids and the running score."""
    derived = offball.derive(r)
    base = sorted(r.events + derived, key=_sort_key)
    shapes = RE.shape_checks(base, r, C.DURATION_S)
    events = sorted(base + shapes, key=_sort_key)
    ids = {}
    score = [0, 0]
    for i, ev in enumerate(events):
        ev["id"] = f"e_{i + 1:04d}"
        ids[id(ev)] = ev["id"]
        ev["_score_before"] = tuple(score)
        if ev["type"] == "shot" and ev["outcome"] == "goal":
            score[0 if ev["team"] == "azc" else 1] += 1
        ev["score"] = {"azc": score[0], "rdm": score[1]}
        if ev["type"] == "free_kick" and ev["from"]:
            fx = ev["from"][0]
            ev["_attacking_third"] = (fx if ev["team"] == "azc" else C.PITCH_L - fx) > 70
    for ev in events:
        ev["related"] = [ids[id(x)] for x in ev.get("related") or [] if id(x) in ids]
    return events


def _event_model(ev: dict, imp: float) -> Event:
    point = lambda p: None if p is None else {"x": float(p[0]), "y": float(p[1])}  # noqa: E731
    return Event.model_validate({
        "id": ev["id"], "t": ev["t"], "type": ev["type"], "team": ev["team"], "player": ev["player"],
        "other": ev.get("other"), "from": point(ev.get("from")), "to": point(ev.get("to")),
        "outcome": ev["outcome"], "xg": ev.get("xg"), "speed_kmh": ev.get("speed_kmh"), "importance": imp,
        "score": ev["score"], "related": ev["related"] or None,
    })


def build_match(world: World, info: MatchInfo) -> MatchFiles:
    """Simulate one library match and return validated Pydantic models for its four files."""
    r = simulate(world, info.seed)
    events = assemble_events(r)
    entries = RE.rate(events)
    max_delta: dict[str, float] = {}
    for e in entries:
        max_delta[e["event_id"]] = max(max_delta.get(e["event_id"], 0.0), abs(e["delta"]))
    event_models = [_event_model(ev, RE.importance(ev, ev["_score_before"], max_delta.get(ev["id"], 0.0),
                                                   info.title_decider)) for ev in events]
    final = events[-1]["score"] if events else {"azc": 0, "rdm": 0}
    teams = sorted(world.teams, key=lambda t: t.id != "azc")
    meta = Meta(
        match_id=info.match_id, schema_version=SCHEMA_VERSION, label=info.label, blurb=info.blurb,
        matchday=info.matchday, seed=info.seed, hero=info.hero, title_decider=info.title_decider,
        duration_s=C.DURATION_S, score=final, default_player=info.default_player,
        teams=[MatchTeam(id=t.id, name=t.name, abbr=t.abbr, formation=t.formation, color=t.color,
                         keeper_color=t.keeper_color,
                         players=[MatchPlayer(**p.model_dump(include={"id", "name", "first_name", "nationality", "number",
                                                                      "position", "slot", "ovr", "gender",
                                                                      "temperament", "attributes"}))
                                  for p in sorted(t.players, key=lambda q: q.number)])
               for t in teams],
        activities=list(ACTIVITIES), entity_order=list(r.entity_order),
    )
    positions = PositionsFile(
        match_id=info.match_id, seconds=C.DURATION_S + 1,
        entities=[EntityTrack(id=e, xy=r.xy[e], act=r.act.get(e)) for e in r.entity_order],
    )
    return MatchFiles(
        meta=meta,
        events=EventsFile(match_id=info.match_id, events=event_models),
        ratings=RatingsFile(match_id=info.match_id, entries=[RatingEntry(**e) for e in entries]),
        positions=positions,
        result=r,
    )


def summary(files: MatchFiles) -> dict[str, Any]:
    """Key numbers for a match: score, scorers, the default player's final rating and top reasons."""
    star = files.meta.default_player
    ev = files.events.events
    entries = [e for e in files.ratings.entries if e.player == star]
    return {
        "score": files.meta.score.model_dump(),
        "scorers": [(e.t, e.player, e.other) for e in ev if e.type == "goal"],
        "star_rating": entries[-1].rating_after if entries else 6.0,
        "star_top": sorted(entries, key=lambda e: -abs(e.delta))[:5],
    }
