"""Match totals used for calibration, the validation report and the seed search (code only, no LLM)."""

from __future__ import annotations

import math
from collections import Counter
from typing import Any

# Benchmark bands per match (ARCHITECTURE section 3). Per-team rows are compared per team.
BENCHMARKS: dict[str, tuple[float, float, str]] = {
    "passes": (850, 940, "Passes (both teams)"),
    "pass_completion": (0.82, 0.84, "Pass completion"),
    "shots": (22, 25, "Shots (both teams)"),
    "shots_on_target": (8, 10, "Shots on target (about 9)"),
    "goals": (2.5, 3.0, "Goals"),
    "pressures_per_team": (115, 175, "Pressures per team"),
    "distance_km": (10, 12, "Distance per outfield player (km)"),
    "fouls_per_team": (10, 12, "Fouls per team"),
}


def match_stats(events: list[dict[str, Any]], xy: dict[str, list[int]], sent_off: dict[str, int] | None = None) -> dict:
    """Totals for one match from its events and recorded positions (decimeters)."""
    c = Counter((e["type"], e["team"]) for e in events)
    passes = [e for e in events if e["type"] in ("pass", "key_pass")]
    shots = [e for e in events if e["type"] == "shot"]
    goals = [e for e in events if e["type"] == "goal"]
    dist: dict[str, float] = {}  # km per outfield player who played the whole match
    for pid, track in xy.items():
        if pid in ("ball", "ref") or pid.endswith("_01") or (sent_off and pid in sent_off):
            continue
        d = sum(math.hypot(track[i] - track[i - 2], track[i + 1] - track[i - 1]) for i in range(2, len(track), 2))
        dist[pid] = d / 10_000
    teams = ("azc", "rdm")
    return {
        "score": {t: sum(g["team"] == t for g in goals) for t in teams},
        "passes": len(passes),
        "pass_completion": sum(e["outcome"] == "success" for e in passes) / max(1, len(passes)),
        "shots": len(shots),
        "shots_on_target": sum(e["outcome"] in ("saved", "goal") for e in shots),
        "goals": len(goals),
        "xg": sum(e["xg"] or 0 for e in shots),
        "pressures": {t: c[("pressure", t)] + c[("counterpress", t)] for t in teams},
        "pressures_per_team": (c[("pressure", "azc")] + c[("counterpress", "azc")]
                               + c[("pressure", "rdm")] + c[("counterpress", "rdm")]) / 2,
        "fouls": {t: c[("foul", t)] for t in teams},
        "fouls_per_team": (c[("foul", "azc")] + c[("foul", "rdm")]) / 2,
        "yellows": c[("card_yellow", "azc")] + c[("card_yellow", "rdm")],
        "reds": c[("card_red", "azc")] + c[("card_red", "rdm")],
        "penalties": c[("penalty", "azc")] + c[("penalty", "rdm")],
        "offsides": c[("offside", "azc")] + c[("offside", "rdm")],
        "corners": c[("corner", "azc")] + c[("corner", "rdm")],
        "injuries": c[("injury", "azc")] + c[("injury", "rdm")],
        "distance_km": _mean(list(dist.values())),
        "distance_by_team": {t: _mean([d for pid, d in dist.items() if pid.startswith(t)]) for t in teams},
        "scorers": [g["player"] for g in goals],
    }


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0
