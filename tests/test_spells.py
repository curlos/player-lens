"""Spell tests: 5-minute windows computed from events only (rating/spells.py)."""

import json
from pathlib import Path

from rating.spells import compute_spells

ROOT = Path(__file__).resolve().parent.parent
LABELS = {"control", "high_press", "end_to_end", "even"}


def hero_events():
    return json.loads((ROOT / "data" / "matches" / "md38_title_decider" / "events.json").read_text())["events"]


def test_windows_cover_the_match():
    spells = compute_spells(hero_events())
    assert len(spells) == 18
    assert spells[0]["start_t"] == 0 and spells[-1]["end_t"] == 5400
    assert all(a["end_t"] == b["start_t"] for a, b in zip(spells, spells[1:]))


def test_values_and_labels_are_consistent():
    events = hero_events()
    spells = compute_spells(events)
    assert sum(s["values"]["goals_azc"] + s["values"]["goals_rdm"] for s in spells) == 5  # every goal lands in a window
    for s in spells:
        v = s["values"]
        assert s["label"] in LABELS
        assert (s["team"] is not None) == (s["label"] in ("control", "high_press"))
        assert abs(v["pass_share_azc"] + v["pass_share_rdm"] - 1) <= 0.011
    assert compute_spells(events) == spells  # deterministic


def test_control_spell_from_synthetic_events():
    events = []
    for i in range(40):  # Azure keep the ball and keep reaching the final third
        events.append({"t": float(i * 5), "type": "pass", "team": "azc", "outcome": "success", "to": {"x": 90.0, "y": 30.0}})
    for i in range(5):
        events.append({"t": float(i * 50), "type": "pass", "team": "rdm", "outcome": "success", "to": {"x": 60.0, "y": 30.0}})
    first = compute_spells(sorted(events, key=lambda e: e["t"]))[0]
    assert (first["label"], first["team"]) == ("control", "azc")
    assert first["values"]["final_third_azc"] == 40 and first["values"]["final_third_rdm"] == 0
