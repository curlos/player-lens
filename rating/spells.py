"""Spells: what each 5-minute window of a match felt like, computed in code from events only.

A spell is commentary context ("Azure have dominated the last ten minutes"), the challenge brief's
explainability patterns (control vs chaos, pressure, rhythm). Spells never change a rating
(specs/match-files.md). Input is the ``events`` list from events.json, so the agent pipeline can call
``compute_spells`` at runtime without positions. Thresholds are guesses in rating/config.py.

Labels, first match wins:
- ``control``: one team has most of the passes and reaches the final third far more (the other is pinned back).
- ``high_press``: one team presses in the opponent half far more than the other.
- ``end_to_end``: many turnovers and shots.
- ``even``: none of the above.
"""

from __future__ import annotations

from typing import Any

from rating import config as RC
from sim import config as C

TEAMS = ("azc", "rdm")


def _attack_x(team: str, x: float) -> float:
    """Meters from the team's own goal line (Azure attacks left to right, Redmond the other way)."""
    return x if team == "azc" else C.PITCH_L - x


def _window_values(events: list[dict[str, Any]]) -> dict[str, Any]:
    """Code-computed numbers for one window: passes, possession share, final-third entries, pressures, turnovers, shots."""
    v: dict[str, Any] = {}
    for team in TEAMS:
        mine = [e for e in events if e["team"] == team]
        passes = [e for e in mine if e["type"] in ("pass", "key_pass")]
        done = [e for e in passes if e["outcome"] == "success"]
        v[f"passes_{team}"] = len(passes)
        v[f"pass_completion_{team}"] = round(len(done) / len(passes), 2) if passes else 0.0
        v[f"final_third_{team}"] = sum(1 for e in done if e.get("to") and _attack_x(team, e["to"]["x"]) > 2 * C.PITCH_L / 3)
        pressures = [e for e in mine if e["type"] in ("pressure", "counterpress")]
        v[f"pressures_{team}"] = len(pressures)
        v[f"high_pressures_{team}"] = sum(1 for e in pressures if e.get("from") and _attack_x(team, e["from"]["x"]) > C.PITCH_L / 2)
        v[f"shots_{team}"] = sum(1 for e in mine if e["type"] == "shot")
        v[f"goals_{team}"] = sum(1 for e in mine if e["type"] == "goal")
    total = v["passes_azc"] + v["passes_rdm"]
    v["pass_share_azc"] = round(v["passes_azc"] / total, 2) if total else 0.5
    v["pass_share_rdm"] = round(1 - v["pass_share_azc"], 2) if total else 0.5
    v["turnovers"] = sum(1 for e in events if e["type"] in ("tackle", "interception"))
    v["passes_per_minute"] = round(total / (RC.SPELL_WINDOW_S / 60), 1)
    return v


def _label(v: dict[str, Any]) -> tuple[str, str | None]:
    for team, other in (("azc", "rdm"), ("rdm", "azc")):
        if (v[f"pass_share_{team}"] >= RC.SPELL_CONTROL_SHARE and v[f"final_third_{team}"] >= RC.SPELL_CONTROL_MIN_ENTRIES
                and v[f"final_third_{team}"] >= RC.SPELL_CONTROL_RATIO * max(1, v[f"final_third_{other}"])):
            return "control", team
    for team, other in (("azc", "rdm"), ("rdm", "azc")):
        if (v[f"high_pressures_{team}"] >= RC.SPELL_PRESS_MIN
                and v[f"high_pressures_{team}"] >= RC.SPELL_PRESS_RATIO * max(1, v[f"high_pressures_{other}"])):
            return "high_press", team
    if v["turnovers"] >= RC.SPELL_CHAOS_TURNOVERS and v["shots_azc"] + v["shots_rdm"] >= RC.SPELL_CHAOS_SHOTS:
        return "end_to_end", None
    return "even", None


def compute_spells(events: list[dict[str, Any]], duration_s: int = C.DURATION_S) -> list[dict[str, Any]]:
    """One spell per 5-minute window: ``{window, start_t, end_t, label, team, values}``.

    ``team`` is the dominant side for ``control`` and ``high_press``, else None. The last window
    includes the final second (t = duration_s).
    """
    size = RC.SPELL_WINDOW_S
    out = []
    for w, start in enumerate(range(0, duration_s, size)):
        end = min(duration_s, start + size)
        last = end == duration_s
        window = [e for e in events if start <= e["t"] < end or (last and e["t"] == end)]
        values = _window_values(window)
        label, team = _label(values)
        out.append({"window": w, "start_t": start, "end_t": end, "label": label, "team": team, "values": values})
    return out
