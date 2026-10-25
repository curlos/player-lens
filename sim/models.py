"""World data models for Player Lens.

Single definition of a valid world (teams, players, attributes). The JSON contract in
``contracts/world.schema.json`` is generated from these models by
``scripts/export_schemas.py``. Source of truth for the rules: specs/roster-generator.md.

Everything here is fictional. Ids are lowercase (``azc_09``).
"""

from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

# Pitch constants (meters). x along the length, y across the width.
PITCH_LENGTH_M = 105.0
PITCH_WIDTH_M = 68.0

# Attributes are integers 25-99 (specs/roster-generator.md).
Rating = Annotated[int, Field(ge=25, le=99)]
HexColor = Annotated[str, Field(pattern=r"^#[0-9A-Fa-f]{6}$")]


class Strict(BaseModel):
    """Unknown fields are errors, so typos fail loudly."""

    model_config = ConfigDict(extra="forbid")


class Position(str, Enum):
    GK = "GK"
    CB = "CB"
    FB = "FB"  # RB / LB
    DM = "DM"
    CM = "CM"
    AM = "AM"
    W = "W"  # RW / LW / RM / LM
    ST = "ST"


class Temperament(str, Enum):
    CALM = "calm"
    NORMAL = "normal"
    HOT_HEADED = "hot-headed"


class Gender(str, Enum):
    MALE = "male"  # always male for now


class Attributes(Strict):
    """Outfield attributes, 25-99. ``shot_stopping`` is for goalkeepers only."""

    pace: Rating
    passing: Rating
    vision: Rating
    finishing: Rating
    dribbling: Rating
    defending: Rating
    positioning: Rating
    composure: Rating
    strength: Rating
    work_rate: Rating
    stamina: Rating
    set_pieces: Rating
    shot_stopping: Rating | None = None


# Shirt number -> (slot, position) per formation. Both CBs use slot "CB".
FORMATION_SLOTS: dict[str, dict[int, tuple[str, Position]]] = {
    "4-3-3": {
        1: ("GK", Position.GK), 2: ("RB", Position.FB), 3: ("LB", Position.FB),
        4: ("CB", Position.CB), 5: ("CB", Position.CB), 6: ("DM", Position.DM),
        8: ("CM", Position.CM), 10: ("AM", Position.AM), 7: ("RW", Position.W),
        9: ("ST", Position.ST), 11: ("LW", Position.W),
    },
    "4-4-2": {
        1: ("GK", Position.GK), 2: ("RB", Position.FB), 3: ("LB", Position.FB),
        4: ("CB", Position.CB), 5: ("CB", Position.CB), 6: ("CM", Position.CM),
        8: ("CM", Position.CM), 7: ("RM", Position.W), 11: ("LM", Position.W),
        9: ("ST", Position.ST), 10: ("ST", Position.ST),
    },
}


class Player(Strict):
    id: str = Field(pattern=r"^[a-z]{3}_\d{2}$")  # e.g. azc_09
    team: str = Field(pattern=r"^[a-z]{3}$")  # lowercase team id, e.g. azc
    name: str = Field(min_length=1)  # "R. Valdemar"
    number: int = Field(ge=1, le=11)
    position: Position
    slot: str = Field(min_length=1)
    gender: Gender = Gender.MALE
    temperament: Temperament
    attributes: Attributes
    ovr: int = Field(ge=25, le=99)

    @model_validator(mode="after")
    def _consistent(self) -> Player:
        errors: list[str] = []
        if self.id != f"{self.team}_{self.number:02d}":
            errors.append(f"{self.id}: id must be {self.team}_{self.number:02d}")
        is_gk = self.position == Position.GK
        if is_gk and self.attributes.shot_stopping is None:
            errors.append(f"{self.id}: goalkeeper needs shot_stopping")
        if not is_gk and self.attributes.shot_stopping is not None:
            errors.append(f"{self.id}: only goalkeepers have shot_stopping")
        if errors:
            raise ValueError("; ".join(errors))
        return self


class Team(Strict):
    id: str = Field(pattern=r"^[a-z]{3}$")  # azc
    name: str = Field(min_length=1)  # Azure City
    abbr: str = Field(pattern=r"^[A-Z]{3}$")  # AZC, shown in the UI
    formation: Literal["4-3-3", "4-4-2"]
    color: HexColor
    keeper_color: HexColor
    players: list[Player] = Field(min_length=11, max_length=11)

    @model_validator(mode="after")
    def _squad_is_valid(self) -> Team:
        errors: list[str] = []
        if self.abbr.lower() != self.id:
            errors.append(f"{self.id}: abbr must be the uppercase id")
        numbers = sorted(p.number for p in self.players)
        if numbers != list(range(1, 12)):
            errors.append(f"{self.id}: shirt numbers must be 1-11, unique (got {numbers})")
        if sum(p.position == Position.GK for p in self.players) != 1:
            errors.append(f"{self.id}: needs exactly 1 goalkeeper")
        if sum(p.temperament == Temperament.HOT_HEADED for p in self.players) > 2:
            errors.append(f"{self.id}: at most 2 hot-headed players")
        slots = FORMATION_SLOTS[self.formation]
        for p in self.players:
            if p.team != self.id:
                errors.append(f"{p.id}: team must be {self.id}")
            expected = slots.get(p.number)
            if expected and (p.slot, p.position) != expected:
                errors.append(f"{p.id}: number {p.number} is {expected[0]}/{expected[1].value} in {self.formation}")
        if errors:
            raise ValueError("; ".join(errors))
        return self


class World(Strict):
    """The whole fictional world: seed and two teams. Written to data/world.json."""

    seed: int
    teams: list[Team] = Field(min_length=2, max_length=2)

    @model_validator(mode="after")
    def _cross_checks(self) -> World:
        errors: list[str] = []
        if len({t.id for t in self.teams}) != 2:
            errors.append("the two teams must have different ids")
        names = [p.name for t in self.teams for p in t.players]
        dupes = sorted({n for n in names if names.count(n) > 1})
        if dupes:
            errors.append(f"duplicate player names: {dupes}")
        if errors:
            raise ValueError("\n".join(errors))
        return self


def load_world(path: str | Path) -> World:
    """Load and validate a world file. Raises pydantic.ValidationError if invalid."""
    return World.model_validate_json(Path(path).read_text(encoding="utf-8"))
