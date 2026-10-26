"""Roster generator tests: the checks in specs/roster-generator.md "Output and validation"."""

import json
from pathlib import Path

import jsonschema
import pytest

from sim.models import World, load_world
from sim.roster import (
    STAR_ATTRIBUTES,
    STAR_ID,
    WORLD_SEED,
    generate_world,
    is_blocked,
    load_blocklist,
    roster_problems,
    world_json,
)

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def world() -> World:
    return generate_world(WORLD_SEED)


def test_generated_world_passes_every_roster_check(world):
    assert roster_problems(world) == []


def test_same_seed_is_byte_identical():
    assert world_json(generate_world(WORLD_SEED)) == world_json(generate_world(WORLD_SEED))


def test_committed_world_matches_generator_and_both_validators(world):
    text = (ROOT / "data" / "world.json").read_text(encoding="utf-8")
    assert text == world_json(world), "data/world.json is stale: run python -m sim.roster"
    schema = json.loads((ROOT / "contracts" / "world.schema.json").read_text(encoding="utf-8"))
    jsonschema.validate(json.loads(text), schema)
    load_world(ROOT / "data" / "world.json")


def test_squads_shape(world):
    for team in world.teams:
        assert sorted(p.number for p in team.players) == list(range(1, 12))
        assert sum(p.position.value == "GK" for p in team.players) == 1
        for p in team.players:
            attrs = p.attributes.model_dump(exclude_none=True)
            assert all(25 <= v <= 99 for v in attrs.values())
            assert (p.attributes.shot_stopping is not None) == (p.position.value == "GK")


def test_star_is_hand_set_and_has_best_set_pieces(world):
    players = {p.id: p for t in world.teams for p in t.players}
    star = players[STAR_ID]
    assert star.attributes.model_dump(exclude_none=True) == STAR_ATTRIBUTES
    assert star.ovr == 91
    assert all(p.attributes.set_pieces < star.attributes.set_pieces for pid, p in players.items() if pid != STAR_ID)
    assert all(p.ovr <= 89 for pid, p in players.items() if pid != STAR_ID)


def test_names_unique(world):
    surnames = [p.name.split(". ", 1)[1] for t in world.teams for p in t.players]
    assert len(set(surnames)) == 22
    for team in world.teams:
        assert len({p.first_name for p in team.players}) == 11


def test_blocklist_matches_ignoring_accents():
    blocklist = load_blocklist()
    assert is_blocked("Thomas", "Müller", blocklist)
    assert is_blocked("Tom", "Van Dijk", blocklist)  # surname-only entry
    assert not is_blocked("Felix", "Müller", blocklist)  # overlapping surnames are fine


def test_problems_are_reported(world):
    broken = world.model_copy(deep=True)
    broken.teams[0].players[3].ovr = 95
    assert any("non-star cap" in p for p in roster_problems(broken))
