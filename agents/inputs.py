"""Code-built inputs for the agent pipeline (specs/agents-backend.md, "Inputs ready from Phase 1").

Everything numeric is computed here and handed to the agents as ``Fact.values``; an LLM may repeat a
number but never makes one up. This module also decides *when* a player gets a line (the cadence
from ARCHITECTURE, "Commentary cadence"), so the Moments agent only adds tone and a reason.

Reads ``meta``, ``events`` and ``ratings`` (and ``positions`` once, for activity and distance).
"""

from __future__ import annotations

import bisect
import json
import math
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

from agents import config as C
from agents.models import Fact, Moment
from rating.spells import compute_spells
from sim.models import Event, EventsFile, MatchPlayer, Meta, RatingEntry, RatingsFile

OFF_BALL_KINDS = {"counterpress", "pressure_regain", "recovery_run", "marking_denial", "decoy_run"}


def minute_of(t: float) -> int:
    """Football minute shown on the clock: 87:12 is 88'."""
    return int(t // 60) + 1


def chunk_of(t: float) -> int:
    """Chunk index for a match second: 0 to 89, the last chunk closed at 5400."""
    return min(int(t // C.CHUNK_S), C.MAX_CHUNK)


@dataclass
class MatchBundle:
    """One match's files, parsed once, plus lazy positions-derived lookups."""

    match_id: str
    meta: Meta
    events: list[Event]
    event_by_id: dict[str, Event]
    ratings: dict[str, list[RatingEntry]]  # per player, in time order
    players: dict[str, MatchPlayer]
    team_of: dict[str, str]
    team_name: dict[str, str]
    spells: list[dict[str, Any]]
    positions_path: Path
    _times: list[float] = field(default_factory=list)
    _positions: dict[str, Any] | None = None
    _cum_km: dict[str, list[float]] = field(default_factory=dict)

    def __deepcopy__(self, memo: dict) -> "MatchBundle":
        """Read-only and large (thousands of events): Agent Framework copies messages between steps, so share it instead."""
        return self

    # -- names and score ---------------------------------------------------------------------------
    def name(self, player_id: str) -> str:
        return self.players[player_id].name if player_id in self.players else player_id

    def score_at(self, t: float) -> dict[str, int]:
        """The score after the last event at or before t (the score field already includes a goal)."""
        i = bisect.bisect_right(self._times, t) - 1
        return self.events[i].score.model_dump() if i >= 0 else {"azc": 0, "rdm": 0}

    # -- positions-derived (read once, only for filler facts) --------------------------------------------
    def _load_positions(self) -> dict[str, Any]:
        if self._positions is None:
            raw = json.loads(self.positions_path.read_text())
            self._positions = {e["id"]: e for e in raw["entities"]}
        return self._positions

    def activity_at(self, player_id: str, t: float) -> str:
        act = self._load_positions()[player_id]["act"]
        return self.meta.activities[act[min(int(t), len(act) - 1)]]

    def pos_at(self, entity: str, t: float) -> tuple[float, float]:
        """An entity's (x, y) in metres at second t (players, "ball"; positions are 1 Hz decimeters)."""
        xy = self._load_positions()[entity]["xy"]
        i = 2 * min(int(t), len(xy) // 2 - 1)
        return xy[i] / 10, xy[i + 1] / 10

    def ball_x_at(self, t: float) -> float:
        """The ball's x in metres at second t (positions are 1 Hz decimeters)."""
        xy = self._load_positions()["ball"]["xy"]
        return xy[2 * min(int(t), len(xy) // 2 - 1)] / 10

    def danger_at(self, t: float) -> str:
        """'azure_attacking' or 'redmond_attacking' when the ball is near a goal at second t, else 'none' (code, not the model)."""
        x = self.ball_x_at(t)
        return "azure_attacking" if x >= C.DANGER_X_HOME_ATTACK else "redmond_attacking" if x <= C.DANGER_X_AWAY_ATTACK else "none"

    def distance_km_at(self, player_id: str, t: float) -> float:
        """Kilometres covered by second t (sum of the 1 Hz steps; positions are decimeters)."""
        cum = self._cum_km.get(player_id)
        if cum is None:
            xy = self._load_positions()[player_id]["xy"]
            cum, total = [0.0], 0.0
            for i in range(1, len(xy) // 2):
                total += math.hypot(xy[2 * i] - xy[2 * i - 2], xy[2 * i + 1] - xy[2 * i - 1]) / 10 / 1000
                cum.append(total)
            self._cum_km[player_id] = cum
        return cum[min(int(t), len(cum) - 1)]


@lru_cache(maxsize=8)
def _load(data_dir: str, match_id: str) -> MatchBundle:
    root = Path(data_dir) / "matches" / match_id
    meta = Meta.model_validate_json((root / "meta.json").read_text())
    events_text = (root / "events.json").read_text()
    events = EventsFile.model_validate_json(events_text).events
    ratings_file = RatingsFile.model_validate_json((root / "ratings.json").read_text())
    ratings: dict[str, list[RatingEntry]] = {}
    for entry in ratings_file.entries:
        ratings.setdefault(entry.player, []).append(entry)
    players = {p.id: p for team in meta.teams for p in team.players}
    team_of = {p.id: team.id for team in meta.teams for p in team.players}
    bundle = MatchBundle(
        match_id=match_id,
        meta=meta,
        events=events,
        event_by_id={e.id: e for e in events},
        ratings=ratings,
        players=players,
        team_of=team_of,
        team_name={team.id: team.name for team in meta.teams},
        # spells read the raw event dicts (events only, no positions)
        spells=compute_spells(json.loads(events_text)["events"]),
        positions_path=root / "positions.json",
        _times=[e.t for e in events],
    )
    return bundle


def load_match(data_dir: str | Path, match_id: str) -> MatchBundle:
    """Loads and caches one match from ``<data_dir>/matches/<match_id>/``."""
    return _load(str(data_dir), match_id)


# --- Facts and the cadence schedule -----------------------------------------------------------------


@dataclass
class PlayerPlan:
    """Everything the pipeline needs for one player in one match: all facts and the scheduled moments."""

    match_id: str
    player_id: str
    facts: dict[str, Fact]
    moments: list[Moment]

    def __deepcopy__(self, memo: dict) -> "PlayerPlan":
        return self  # read-only and shared, like the match bundle

    def chunk_moments(self, chunk: int) -> list[Moment]:
        return [m for m in self.moments if chunk_of(m.t) == chunk]

    def facts_for(self, moments: list[Moment]) -> list[Fact]:
        ids = {fid for m in moments for fid in m.fact_ids}
        return [f for fid, f in self.facts.items() if fid in ids]


def default_tone(importance: float) -> str:
    """Tone from code importance (the Moments agent may refine it): 0.8+ excited, 0.4+ building, else calm."""
    if importance >= C.BIG_IMPORTANCE:
        return "excited"
    return "building" if importance >= 0.4 else "calm"


class _Builder:
    """Creates facts and candidate moments for one player."""

    def __init__(self, bundle: MatchBundle, player_id: str):
        self.b = bundle
        self.player = player_id
        self.facts: dict[str, Fact] = {}
        self.candidates: list[dict[str, Any]] = []
        self._spell_facts: dict[int, str] = {}
        self._last_activity = ""  # the selected player's activity as last said (stat and play lines mention it only on a change)
        self._activity_said_t = -math.inf
        self._stat_count = 0  # rotates the stat-line topic

    def fact(self, t: float, kind: str, player_id: str, event_ids: list[str], values: dict[str, Any]) -> str:
        fid = f"f_{len(self.facts) + 1:04d}"
        self.facts[fid] = Fact(fact_id=fid, t=t, kind=kind, player_id=player_id, event_ids=event_ids, values=values)  # type: ignore[arg-type]
        return fid

    # -- match-wide moments: goals, cards, penalties --------------------------------------------------
    def highlights(self) -> set[float]:
        """Adds goal, card and penalty candidates; returns the seconds where the player is involved."""
        b, me = self.b, self.player
        involved_seconds: set[float] = set()
        reds = {(e.player, e.t) for e in b.events if e.type == "card_red"}
        for e in b.events:
            if e.type not in ("goal", "card_yellow", "card_red", "penalty"):
                continue
            if e.type == "card_yellow" and (e.player, e.t) in reds:
                continue  # a second yellow is merged into its red
            involved = me in (e.player, e.other)
            if involved:
                involved_seconds.add(e.t)
            event_ids = [e.id, *(e.related or [])]
            team = b.team_name[e.team]
            if e.type == "goal":
                shot = next((s for s in b.events if s.type == "shot" and s.t == e.t and s.player == e.player), None)
                values: dict[str, Any] = {
                    "scorer": b.name(e.player), "team": team, "minute": minute_of(e.t),
                    "score": f"{e.score.azc}-{e.score.rdm}",
                    "goals_so_far": sum(1 for g in b.events if g.type == "goal" and g.player == e.player and g.t <= e.t),
                    "selected_scored": e.player == me, "selected_assisted": e.other == me,
                }
                if e.other:
                    values["assister"] = b.name(e.other)
                if e.xg is not None:
                    values["xg"] = round(e.xg, 2)
                if shot and shot.speed_kmh:
                    values["shot_speed_kmh"] = round(shot.speed_kmh)
                kind, trigger = "goal", "goal"
            elif e.type == "penalty":
                values = {"action": "penalty awarded", "team": team, "minute": minute_of(e.t)}
                kind, trigger = "foul", "penalty"
            else:
                red = e.type == "card_red"
                values = {"player": b.name(e.player), "team": team, "minute": minute_of(e.t), "card": "red" if red else "yellow"}
                if red and any(y.type == "card_yellow" and y.player == e.player and y.t <= e.t for y in b.events):
                    values["second_yellow"] = True
                kind, trigger = "card", "card"
            fid = self.fact(e.t, kind, e.player, event_ids, values)
            fids = [fid]
            if involved:  # the selected player's rating change in that second explains the jump
                rating = self.rating_fact(e.t)
                if rating:
                    fids.append(rating)
            importance = 1.0 if involved else e.importance
            self.candidates.append({"t": e.t, "trigger": trigger, "importance": importance, "fact_ids": fids})
            if e.type == "goal":
                self.candidates.append({
                    "t": min(e.t + C.REACTION_DELAY_S, b.meta.duration_s), "trigger": "reaction",
                    "importance": C.REACTION_IMPORTANCE, "fact_ids": [fid],
                })
        return involved_seconds

    def rating_fact(self, t: float) -> str | None:
        """One rating_change fact for the player's total change at second t (delta and rating from the log)."""
        group = [r for r in self.b.ratings.get(self.player, []) if r.t == t and r.delta != 0]
        if not group:
            return None
        delta = round(sum(r.delta for r in group), 2)
        return self.fact(t, "rating_change", self.player, [r.id for r in group],
                         {"delta": delta, "rating_after": round(group[-1].rating_after, 1), "reason_code": max(group, key=lambda r: abs(r.delta)).reason_code})

    # -- the selected player's own rating-log moments ----------------------------------------------------
    def rating_moments(self, skip_seconds: set[float]) -> None:
        b = self.b
        groups: dict[float, list[RatingEntry]] = {}
        for r in b.ratings.get(self.player, []):
            if r.delta == 0 or r.t in skip_seconds:  # every row the rating log shows (it hides only 0.00)
                continue
            groups.setdefault(r.t, []).append(r)
        for t, group in sorted(groups.items()):
            top = max(group, key=lambda r: abs(r.delta))
            kind = C.REASON_KIND.get(top.reason_code, "rating_change")
            delta = round(sum(r.delta for r in group), 2)
            if kind in OFF_BALL_KINDS:
                trigger = "off_ball"
            elif kind in C.KEY_EVENT_KINDS:
                trigger = "key_event"
            else:
                trigger = "rating_change"
            values: dict[str, Any] = {"reason_code": top.reason_code, "delta": delta, "rating_after": round(group[-1].rating_after, 1),
                                      "minute": minute_of(t), "off_ball": any(r.off_ball for r in group)}
            for key, val in top.values.items():
                values[key] = b.name(val) if key in C.NAME_KEYS and isinstance(val, str) else val
            event = b.event_by_id.get(top.event_id)
            event_ids = [top.event_id, *(event.related or [] if event else []), *(r.id for r in group)]
            fid = self.fact(t, kind, self.player, event_ids, values)
            importance = max(event.importance if event else 0.1, C.RATING_LINE_IMPORTANCE)
            self.candidates.append({"t": t, "trigger": trigger, "importance": importance, "fact_ids": [fid], "rating": True})

    # -- spells and fillers ---------------------------------------------------------------------------
    def spell_fact(self, t: float) -> str | None:
        """The 5-minute spell fact for the window containing t; None for an 'even' spell (nothing to say)."""
        window = int(t // C.SPELL_WINDOW_S)
        if window not in self._spell_facts:
            spell = self.b.spells[min(window, len(self.b.spells) - 1)]
            if spell["label"] == "even":
                self._spell_facts[window] = ""
            else:
                v = spell["values"]
                values: dict[str, Any] = {
                    "label": spell["label"], "team": self.b.team_name.get(spell["team"], "") if spell["team"] else "",
                    "from_minute": minute_of(spell["start_t"]), "to_minute": minute_of(spell["end_t"] - 1),
                }
                for key in ("pass_share_azc", "pass_share_rdm", "final_third_azc", "final_third_rdm", "high_pressures_azc",
                            "high_pressures_rdm", "shots_azc", "shots_rdm"):
                    values[key] = v[key]
                self._spell_facts[window] = self.fact(spell["start_t"], "spell", self.player, [f"spell:{spell['window']}"], values)
        return self._spell_facts[window] or None

    def play_fact(self, t: float) -> str | None:
        """What is happening around the ball at second t, for a quiet spell: the latest on-ball event near t (code-built)."""
        b = self.b
        lo, hi = t - C.PLAY_WINDOW_S[0], t + C.PLAY_WINDOW_S[1]
        near = [e for e in b.events if lo <= e.t <= hi and e.type in C.PLAY_ACTIONS]
        if not near:
            return None
        me = b.pos_at(self.player, t)

        def close(e: Event) -> bool:  # the event's player is near the selected player: keeps him in the picture
            px, py = b.pos_at(e.player, e.t)
            return math.hypot(px - me[0], py - me[1]) <= C.PLAY_NEAR_M or self.player in (e.player, e.other)

        e = max(near, key=lambda e: (close(e), e.t, e.importance))
        x = b.ball_x_at(e.t)
        home, away = b.team_name[C.HOME_TEAM], b.team_name["rdm"]
        if x >= 88:  # Azure City attack left to right all match
            zone, zone_es = f"on the edge of the {away} box", f"cerca del área de {away}"
        elif x >= 70:
            zone, zone_es = f"in {away}'s half", f"en campo de {away}"
        elif x > 35:
            zone, zone_es = "in midfield", "en el mediocampo"
        elif x > 17:
            zone, zone_es = f"in {home}'s half", f"en campo de {home}"
        else:
            zone, zone_es = f"on the edge of the {home} box", f"cerca del área de {home}"
        values: dict[str, Any] = {
            "action": C.PLAY_ACTIONS[e.type], "event": e.type.replace("_", " "), "actor": b.name(e.player), "team": b.team_name[e.team],
            "zone": zone, "zone_es": zone_es, "minute": minute_of(t), "selected_near_ball": close(e),
        }
        activity = b.activity_at(self.player, t)
        if activity != self._last_activity and t - self._activity_said_t >= C.ACTIVITY_REPEAT_S:  # only news is worth saying
            values["selected_activity"] = activity
            self._last_activity, self._activity_said_t = activity, t
        if e.other and e.other in b.players:
            values["receiver" if C.PLAY_ACTIONS[e.type] == "pass" else "opponent"] = b.name(e.other)
        return self.fact(t, "play", e.player, [e.id], values)

    def filler_fact(self, t: float) -> str:
        """A stat line about the selected player on ONE topic, rotating distance, rating and activity (activity only if it changed)."""
        b = self.b
        activity = b.activity_at(self.player, t)
        topics = [x for x in C.STAT_TOPICS if x != "activity" or activity != self._last_activity]
        topic = topics[self._stat_count % len(topics)]
        self._stat_count += 1
        values: dict[str, Any] = {"minute": minute_of(t), "score": "{azc}-{rdm}".format(**b.score_at(t)), "topic": topic}
        if topic == "distance":
            values["distance_km"] = round(b.distance_km_at(self.player, t), 1)
        elif topic == "rating":
            values["rating"] = round(self._rating_at(t), 1)
        else:
            values["activity"] = activity
            self._last_activity, self._activity_said_t = activity, t
        return self.fact(t, "filler_stat", self.player, [f"stat:{self.player}:{int(t)}"], values)

    def _rating_at(self, t: float) -> float:
        rating = 6.0
        for r in self.b.ratings.get(self.player, []):
            if r.t > t:
                break
            rating = r.rating_after
        return rating

    # -- cadence ---------------------------------------------------------------------------------------
    def schedule(self) -> list[Moment]:
        """Picks which candidates become lines: 5 s minimum gap (big moments may interrupt); a stat line only after LINE_MAX_SILENCE_S of silence.

        A rating-log moment is never dropped: too close to the previous line it waits (up to RATING_MAX_DELAY_S),
        and failing that it joins the previous rating line, so every visible rating change is commented on.
        """
        duration = self.b.meta.duration_s
        picked: list[dict[str, Any]] = []
        prev_end = -math.inf
        for c in sorted(self.candidates, key=lambda c: (c["t"], -c["importance"])):
            big = c["importance"] >= C.BIG_IMPORTANCE
            min_gap = 0 if c["trigger"] == "reaction" else C.LINE_MIN_GAP_S  # the reaction is part of the goal moment
            if not big and c["t"] < prev_end + min_gap:
                if not c.get("rating"):
                    continue
                later = min(float(math.ceil(prev_end + min_gap)), float(duration))  # wait for the line before it, never past full time
                if c["t"] < later <= c["t"] + C.RATING_MAX_DELAY_S:
                    c = {**c, "t": later}
                else:
                    host = next((p for p in reversed(picked) if p.get("rating")), None)
                    if host is None:
                        continue
                    host["fact_ids"] = [*host["fact_ids"], *c["fact_ids"]]  # said together with the previous rating line
                    continue
            if big and picked and picked[-1]["t"] == c["t"]:
                if c.get("rating"):  # e.g. the keeper's goal-conceded row: said with the goal line, never dropped
                    picked[-1]["fact_ids"] = [*picked[-1]["fact_ids"], *c["fact_ids"]]
                continue
            picked.append({**c})  # a copy: a later rating moment may join it
            prev_end = max(prev_end, c["t"] + C.LINE_EST_S)
        picked.sort(key=lambda c: c["t"])

        final: list[dict[str, Any]] = []
        last_end = 0.0
        last_stat = -math.inf

        def fill_until(until: float) -> None:
            """Quiet spells: a line about the game around the ball, or (at most every STAT_EVERY_S) a stat about the player."""
            nonlocal last_end, last_stat
            while until - last_end > C.LINE_MAX_SILENCE_S:
                # FILLER_AFTER_S after the last line, but never so late the next line loses its minimum gap
                t = round(last_end + min(C.FILLER_AFTER_S, (until - last_end - C.LINE_EST_S) / 2))
                if t >= duration:
                    break
                stat_due = t - last_stat >= C.STAT_EVERY_S
                play = None if stat_due else self.play_fact(t)
                if play:
                    final.append({"t": float(t), "trigger": "play", "importance": C.PLAY_IMPORTANCE, "fact_ids": [play]})
                elif stat_due:
                    final.append({"t": float(t), "trigger": "filler", "importance": C.FILLER_IMPORTANCE, "fact_ids": [self.filler_fact(t)]})
                    last_stat = t
                else:  # nothing on the ball to call and no stat due: stay quiet a little longer and look again
                    last_end = float(t)
                    continue
                last_end = t + C.LINE_EST_S

        for c in picked:
            fill_until(c["t"])
            final.append(c)
            last_end = c["t"] + C.LINE_EST_S
        fill_until(duration)

        moments = []
        for i, c in enumerate(final, start=1):
            fact_ids = list(c["fact_ids"])
            spell = self.spell_fact(c["t"]) if c["trigger"] != "reaction" else None
            if spell:
                fact_ids.append(spell)
            moments.append(Moment(moment_id=f"m_{i:04d}", t=c["t"], trigger=c["trigger"], importance=round(c["importance"], 2),
                                  tone=default_tone(c["importance"]), fact_ids=fact_ids))  # type: ignore[arg-type]
        return moments


@lru_cache(maxsize=16)
def _plan(data_dir: str, match_id: str, player_id: str) -> PlayerPlan:
    bundle = load_match(data_dir, match_id)
    if player_id not in bundle.players:
        raise KeyError(player_id)
    builder = _Builder(bundle, player_id)
    involved = builder.highlights()
    builder.rating_moments(involved)
    moments = builder.schedule()
    return PlayerPlan(match_id=match_id, player_id=player_id, facts=builder.facts, moments=moments)


def build_plan(data_dir: str | Path, match_id: str, player_id: str) -> PlayerPlan:
    """All facts and scheduled moments for one player in one match (cached; deterministic)."""
    return _plan(str(data_dir), match_id, player_id)


def home_side(fact: Fact, bundle: MatchBundle) -> str:
    """'good', 'bad' or 'neutral' for Azure City, the commentators' team (code decides this, never the model).

    Goals and penalties go by the team that gains; cards go against the carded player's team; rating moments go by the sign
    of the delta and the player's team; spells by the dominant team; filler stats by the score at that moment (a home
    commentator sounds happier when Azure City lead and more anxious when they trail).
    """
    home = bundle.team_name[C.HOME_TEAM]
    v = fact.values
    if fact.kind == "filler_stat":
        azc, rdm = (int(x) for x in str(v.get("score", "0-0")).split("-"))  # the score is always "azc-rdm"
        return "good" if azc > rdm else "bad" if azc < rdm else "neutral"
    if fact.kind == "spell" and not v.get("team"):
        return "neutral"
    if fact.kind == "play":  # an attack is good or bad news; play in midfield is neutral
        zone = str(v.get("zone", ""))
        if v.get("team") == home and bundle.team_name["rdm"] in zone:
            return "good"
        if v.get("team") != home and home in zone:
            return "bad"
        return "neutral"
    if fact.kind in ("goal", "spell") or (fact.kind == "foul" and v.get("action") == "penalty awarded"):
        return "good" if v.get("team") == home else "bad"
    if fact.kind == "card":
        return "bad" if v.get("team") == home else "good"
    ours = bundle.team_of.get(fact.player_id) == C.HOME_TEAM
    delta = v.get("delta")
    if isinstance(delta, (int, float)) and delta == 0:
        return "neutral"
    went_well = not isinstance(delta, (int, float)) or delta > 0  # an action fact without a delta is a positive action
    return "good" if went_well == ours else "bad"


def chunk_context(bundle: MatchBundle, player_id: str, chunk: int) -> dict[str, Any]:
    """The shared input every agent sees for one chunk: who, when, the score and the team shapes."""
    p = bundle.players[player_id]
    start = chunk * C.CHUNK_S
    end = bundle.meta.duration_s if chunk == C.MAX_CHUNK else start + C.CHUNK_S
    return {
        "match_id": bundle.match_id,
        "player": {"id": p.id, "name": p.name, "number": p.number, "position": p.slot, "team": bundle.team_name[bundle.team_of[p.id]],
                   "gender": p.gender.value},
        "window": {"start_t": start, "end_t": end, "chunk": chunk},
        "score_at_start": bundle.score_at(start),
        "teams": {t.id: {"name": t.name, "abbr": t.abbr, "formation": t.formation} for t in bundle.meta.teams},
    }
