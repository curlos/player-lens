"""World model tests: the roster rules from specs/roster-generator.md that the JSON schema cannot express."""

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from sim.models import FORMATION_SLOTS, Nationality, Player, Position, World

ROOT = Path(__file__).resolve().parent.parent

# Fixed fictional names so the test world is deterministic and has no shared surnames.
SURNAMES = [
    "Smith", "García", "Silva", "Martin", "Müller", "Costa", "Gruber", "De Jong", "Rossi", "Jones", "Lopez",
    "Brown", "Ruiz", "Lima", "Petit", "Weber", "Alves", "Huber", "Bakker", "Bianchi", "Taylor", "Pérez",
]


def attributes(is_gk: bool) -> dict:
    values = {k: 70 for k in (
        "pace", "passing", "vision", "finishing", "dribbling", "defending",
        "positioning", "composure", "strength", "work_rate", "stamina", "set_pieces",
    )}
    if is_gk:
        values["shot_stopping"] = 70
    return values


def make_team(team_id: str, formation: str, surnames: list[str]) -> dict:
    players = []
    for (number, (slot, position)), surname in zip(sorted(FORMATION_SLOTS[formation].items()), surnames):
        first_name = f"Name{number}"
        players.append({
            "id": f"{team_id}_{number:02d}", "team": team_id,
            "name": f"{first_name[0]}. {surname}", "first_name": first_name,
            "nationality": Nationality.ENGLAND.value, "number": number,
            "position": position.value, "slot": slot, "gender": "male", "temperament": "normal",
            "attributes": attributes(position == Position.GK), "ovr": 70,
        })
    return {
        "id": team_id, "name": team_id.upper(), "abbr": team_id.upper(), "formation": formation,
        "color": "#3B82F6", "keeper_color": "#E6F23A", "players": players,
    }


@pytest.fixture
def world_dict() -> dict:
    return {"seed": 1, "teams": [make_team("azc", "4-3-3", SURNAMES[:11]), make_team("rdm", "4-4-2", SURNAMES[11:])]}


def test_valid_world_loads(world_dict):
    world = World.model_validate_json(json.dumps(world_dict))
    assert world.teams[0].players[0].first_name == "Name1"
    assert world.teams[0].players[0].nationality == Nationality.ENGLAND


@pytest.mark.parametrize("field", ["first_name", "nationality"])
def test_player_requires_new_fields(world_dict, field):
    del world_dict["teams"][0]["players"][0][field]
    with pytest.raises(ValidationError):
        World.model_validate_json(json.dumps(world_dict))


def test_unknown_nationality_is_rejected(world_dict):
    world_dict["teams"][0]["players"][0]["nationality"] = "Atlantis"
    with pytest.raises(ValidationError):
        World.model_validate_json(json.dumps(world_dict))


def test_exported_schema_contains_new_fields():
    schema = json.loads((ROOT / "contracts" / "world.schema.json").read_text(encoding="utf-8"))
    player = schema["$defs"]["Player"]
    assert {"first_name", "nationality"} <= set(player["required"])
    assert schema == World.model_json_schema(), "contracts/world.schema.json is stale: run scripts/export_schemas.py"


def test_player_model_accepts_a_single_valid_entry(world_dict):
    Player.model_validate(world_dict["teams"][0]["players"][0])
