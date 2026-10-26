"""Contract tests: every schema in contracts/ is current with its Pydantic model."""

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from scripts.export_schemas import CONTRACTS
from sim.models import Event

ROOT = Path(__file__).resolve().parent.parent


@pytest.mark.parametrize("filename", sorted(CONTRACTS))
def test_schema_is_current(filename):
    schema = json.loads((ROOT / "contracts" / filename).read_text(encoding="utf-8"))
    assert schema == CONTRACTS[filename].model_json_schema(), f"contracts/{filename} is stale: run scripts/export_schemas.py"


def test_event_uses_from_alias():
    ev = Event.model_validate({
        "id": "e_0001", "t": 12.0, "type": "pass", "team": "azc", "player": "azc_06", "other": "azc_09",
        "from": {"x": 40.0, "y": 30.0}, "to": {"x": 55.0, "y": 31.0}, "outcome": "success",
        "importance": 0.05, "score": {"azc": 0, "rdm": 0},
    })
    assert ev.from_.x == 40.0
    assert "from" in ev.model_dump(by_alias=True)


def test_event_rejects_unknown_type():
    with pytest.raises(ValidationError):
        Event.model_validate({
            "id": "e_0001", "t": 1, "type": "teleport", "team": "azc", "player": "azc_06",
            "outcome": "none", "importance": 0, "score": {"azc": 0, "rdm": 0},
        })
