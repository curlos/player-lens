"""Match-file tests: the committed library files validate, regenerate byte-identically and match the brief."""

import json
from pathlib import Path

import pytest

from sim.library import BACKUPS, LIBRARY
from sim.models import EventsFile, Meta, PositionsFile, RatingsFile, load_world
from sim.pipeline import build_match
from sim.validate import match_problems, schema_problems

ROOT = Path(__file__).resolve().parent.parent
MATCHES = ROOT / "data" / "matches"
NAMES = ("meta.json", "events.json", "ratings.json", "positions.json")
BY_ID = {m.match_id: m for m in LIBRARY + BACKUPS}


def load_texts(match_id: str) -> dict[str, str]:
    return {n: (MATCHES / match_id / n).read_text(encoding="utf-8") for n in NAMES}


def load_models(texts: dict[str, str]):
    return (Meta.model_validate_json(texts["meta.json"]), EventsFile.model_validate_json(texts["events.json"]),
            RatingsFile.model_validate_json(texts["ratings.json"]), PositionsFile.model_validate_json(texts["positions.json"]))


@pytest.mark.parametrize("match_id", sorted(BY_ID))
def test_library_match_validates(match_id):
    texts = load_texts(match_id)
    assert schema_problems(texts) == []
    meta, events, ratings, positions = load_models(texts)
    assert match_problems(meta, events, ratings, positions) == []
    assert meta.seed == BY_ID[match_id].seed and meta.match_id == match_id


@pytest.mark.parametrize("match_id", sorted(BY_ID))
def test_library_match_regenerates_byte_identically(match_id):
    files = build_match(load_world(ROOT / "data" / "world.json"), BY_ID[match_id])
    assert files.texts() == load_texts(match_id), f"{match_id} is stale: run python -m sim.run --library"


def _goals(match_id):
    events = json.loads(load_texts(match_id)["events.json"])["events"]
    return [e for e in events if e["type"] == "goal"]


def test_hero_match_is_azure_3_2_with_two_star_goals():
    meta, *_ = load_models(load_texts("md38_title_decider"))
    assert meta.hero and meta.title_decider and meta.matchday == 38
    assert (meta.score.azc, meta.score.rdm) == (3, 2)
    scorers = [g["player"] for g in _goals("md38_title_decider")]
    assert scorers.count(meta.default_player) == 2 and meta.default_player == "azc_09"
    events = json.loads(load_texts("md38_title_decider")["events.json"])["events"]
    assert not any(e["type"] == "injury" for e in events)  # none in the hero match (specs/match-rules.md)
    # Owner pick (Oct 26): level at 2-2 until the star scores the last goal, a winner at 85' or later.
    goals = _goals("md38_title_decider")
    assert goals[-1]["player"] == "azc_09" and goals[-1]["t"] >= 85 * 60
    assert goals[-2]["score"] == {"azc": 2, "rdm": 2}


def test_only_one_hero_is_listed():
    assert [m.match_id for m in LIBRARY if m.hero] == ["md38_title_decider"]
    assert len(LIBRARY) == 3 and not any(m.hero for m in BACKUPS)


def test_other_library_results():
    blow, *_ = load_models(load_texts("md19_blowout"))
    assert blow.score.rdm == 0 and blow.score.azc in (4, 5)
    draw, *_ = load_models(load_texts("md27_draw"))
    assert (draw.score.azc, draw.score.rdm) == (1, 1)


def test_unique_event_ids_and_rating_references_across_files():
    for match_id in BY_ID:
        _meta, events, ratings, _pos = load_models(load_texts(match_id))
        ids = [e.id for e in events.events]
        assert len(ids) == len(set(ids))
        assert {r.event_id for r in ratings.entries} <= set(ids)


def test_validator_catches_broken_files():
    meta, events, ratings, positions = load_models(load_texts("md38_title_decider"))
    ratings.entries[5].rating_after += 0.5
    meta.score.azc += 1
    events.match_id = "md19_blowout"
    positions.entities[1].act[3] = len(meta.activities)
    positions.entities[0].xy[2] += 200  # a 20 m jump in one second
    problems = match_problems(meta, events, ratings, positions)
    assert any("rating_after" in p for p in problems)
    assert any("meta.score" in p for p in problems)
    assert any("moved" in p for p in problems)
    assert any("different matches" in p for p in problems)
    assert any("activity index" in p for p in problems)
