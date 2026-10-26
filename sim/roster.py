"""Roster generator: builds both squads once and writes data/world.json (specs/roster-generator.md).

Run from the repo root:  python -m sim.roster [--seed 2026]

Pure Python, seeded, no network, no LLM. Same seed gives a byte-identical file.
"""

from __future__ import annotations

import argparse
import json
import re
import unicodedata
from pathlib import Path

import numpy as np

from sim.models import (
    FORMATION_SLOTS,
    Attributes,
    Gender,
    Nationality,
    Player,
    Position,
    Team,
    Temperament,
    World,
)
from sim.names import FIRST_NAMES, SURNAMES

ROOT = Path(__file__).resolve().parent.parent
WORLD_PATH = ROOT / "data" / "world.json"
BLOCKLIST_PATH = Path(__file__).with_name("blocklist.txt")

# ---------------------------------------------------------------------------
# Tuning knobs (guesses from general knowledge of top squads, not researched data)
# ---------------------------------------------------------------------------
WORLD_SEED = 2026
ATTR_SD = 6.0  # per-attribute noise
QUALITY_SD = 6.0  # per-player quality offset, applied to every attribute
NON_STAR_OVR_CAP = 89
SET_PIECES_CAP = 92  # everyone but the star, so the star always takes Azure's penalties
TEMPERAMENT_P = {Temperament.CALM: 0.25, Temperament.NORMAL: 0.60, Temperament.HOT_HEADED: 0.15}
MAX_HOT_HEADED = 2
MAX_ATTEMPTS = 50  # deterministic retries (sub-seeds) until every roster check passes

ATTR_NAMES = ("pace", "passing", "vision", "finishing", "dribbling", "defending", "positioning",
              "composure", "strength", "work_rate", "stamina", "set_pieces")
HIGH, MEDIUM, LOW, OTHER = 80.0, 68.0, 50.0, 60.0

# Position templates: (high, medium, low) attribute lists; unlisted attributes use OTHER.
TEMPLATES: dict[Position, tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...]]] = {
    Position.GK: (("shot_stopping", "composure", "positioning"), ("passing", "strength"), ("pace", "dribbling", "finishing")),
    Position.CB: (("defending", "strength", "positioning"), ("composure", "stamina", "passing"), ("dribbling", "finishing", "vision")),
    Position.FB: (("pace", "stamina", "work_rate"), ("defending", "passing", "dribbling"), ("finishing", "vision")),
    Position.DM: (("defending", "positioning", "work_rate"), ("passing", "stamina", "strength"), ("finishing", "dribbling")),
    Position.CM: (("passing", "vision", "stamina"), ("positioning", "work_rate", "dribbling"), ("defending", "finishing")),
    Position.AM: (("vision", "passing", "dribbling"), ("finishing", "composure", "set_pieces"), ("defending", "strength")),
    Position.W: (("pace", "dribbling", "passing"), ("finishing", "stamina", "vision"), ("defending", "strength")),
    Position.ST: (("finishing", "composure", "positioning"), ("pace", "strength", "dribbling"), ("defending", "work_rate")),
}

TEAM_DEFS = [
    {"id": "azc", "name": "Azure City", "abbr": "AZC", "formation": "4-3-3", "color": "#3B82F6",
     "keeper_color": "#E6F23A", "target_ovr": 78.0},
    {"id": "rdm", "name": "Redmond United", "abbr": "RDM", "formation": "4-4-2", "color": "#E5484D",
     "keeper_color": "#FF9F1C", "target_ovr": 74.0},
]
TEAM_OVR_TOLERANCE = 2.0
MIN_STRONG = {"azc": 2, "rdm": 1}  # players at OVR 80+
MIN_OVR_SD = 4.0

STAR_ID = "azc_09"
STAR_OVR = 91
STAR_ATTRIBUTES = {
    "finishing": 94, "composure": 92, "positioning": 92, "pace": 88, "dribbling": 87, "strength": 84,
    "vision": 78, "passing": 76, "work_rate": 80, "stamina": 82, "defending": 40, "set_pieces": 93,
}
RDM_SET_PIECE_TAKER = "rdm_08"  # designated taker: Set pieces mean 85
TAKER_SET_PIECES_MEAN = 85.0


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fold(text: str) -> str:
    """Lowercase and strip accents, so 'Müller' matches 'Muller'."""
    return "".join(c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c)).lower().strip()


def load_blocklist(path: Path = BLOCKLIST_PATH) -> tuple[set[str], set[str]]:
    """Return (blocked surnames, blocked full names), folded."""
    surnames, full = set(), set()
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("surname:"):
            surnames.add(_fold(line.removeprefix("surname:")))
        else:
            (full if " " in line else surnames).add(_fold(line))
    return surnames, full


def is_blocked(first: str, surname: str, blocklist: tuple[set[str], set[str]]) -> bool:
    surnames, full = blocklist
    return _fold(surname) in surnames or _fold(f"{first} {surname}") in full


def syllables(word: str) -> int:
    """Rough English syllable count: vowel groups."""
    return len(re.findall(r"[aeiouy]+", _fold(word)))


def is_star_surname(surname: str) -> bool:
    """Short (one or two syllables), one word, plain ASCII letters: easy to say aloud in English."""
    return surname.isascii() and surname.isalpha() and syllables(surname) <= 2


def compute_ovr(position: Position, attrs: dict[str, int]) -> int:
    """Weighted mean of the position's High, Medium and Low attributes (weights 3, 2, 1), rounded."""
    high, medium, low = TEMPLATES[position]
    total = 3 * sum(attrs[a] for a in high) + 2 * sum(attrs[a] for a in medium) + sum(attrs[a] for a in low)
    return int(round(total / (3 * len(high) + 2 * len(medium) + len(low))))


def _template_mean(position: Position, attr: str) -> float:
    high, medium, low = TEMPLATES[position]
    return HIGH if attr in high else MEDIUM if attr in medium else LOW if attr in low else OTHER


def _clamp(value: float, lo: int = 25, hi: int = 99) -> int:
    return int(min(hi, max(lo, round(value))))


# ---------------------------------------------------------------------------
# Generation
# ---------------------------------------------------------------------------

class _Draft:
    """A player's random draws, fixed before the team offset is solved."""

    def __init__(self, team_id: str, number: int, slot: str, position: Position, rng: np.random.Generator):
        self.id = f"{team_id}_{number:02d}"
        self.team = team_id
        self.number, self.slot, self.position = number, slot, position
        self.is_star = self.id == STAR_ID
        self.quality = 0.0 if self.is_star else float(rng.normal(0.0, QUALITY_SD))
        self.noise = {a: float(rng.normal(0.0, 1.0)) for a in (*ATTR_NAMES, "shot_stopping")}

    def attributes(self, team_offset: float) -> dict[str, int]:
        if self.is_star:
            return dict(STAR_ATTRIBUTES)
        attrs: dict[str, int] = {}
        names = ATTR_NAMES + (("shot_stopping",) if self.position == Position.GK else ())
        for a in names:
            mean = _template_mean(self.position, a) + team_offset + self.quality
            if a == "set_pieces" and self.id == RDM_SET_PIECE_TAKER:
                mean = TAKER_SET_PIECES_MEAN
            attrs[a] = _clamp(mean + ATTR_SD * self.noise[a])
        attrs["set_pieces"] = min(attrs["set_pieces"], SET_PIECES_CAP)
        return attrs

    def ovr(self, team_offset: float) -> int:
        return STAR_OVR if self.is_star else compute_ovr(self.position, self.attributes(team_offset))


def _solve_team(drafts: list[_Draft], target: float) -> float:
    """Find the team offset whose mean OVR is closest to target, then pull any non-star above the cap down."""
    def mean_ovr(offset: float) -> float:
        return float(np.mean([d.ovr(offset) for d in drafts]))

    lo, hi = -15.0, 30.0
    for _ in range(40):  # bisection: mean OVR rises with the offset
        mid = (lo + hi) / 2
        if mean_ovr(mid) < target:
            lo = mid
        else:
            hi = mid
    offset = (lo + hi) / 2
    for _ in range(5):
        for d in drafts:
            while not d.is_star and d.ovr(offset) > NON_STAR_OVR_CAP:
                d.quality -= 0.5
        lo, hi = offset - 5, offset + 5
        for _ in range(30):
            mid = (lo + hi) / 2
            if mean_ovr(mid) < target:
                lo = mid
            else:
                hi = mid
        offset = (lo + hi) / 2
    return offset


def _draw_nationalities(rng: np.random.Generator) -> list[Nationality]:
    pool = list(Nationality)
    while True:
        picks = [pool[int(i)] for i in rng.integers(0, len(pool), size=11)]
        counts = [picks.count(n) for n in set(picks)]
        if len(counts) >= 3 and max(counts) <= 4:
            return picks


def _draw_temperament(rng: np.random.Generator, hot_so_far: int) -> Temperament:
    options = list(TEMPERAMENT_P)
    pick = options[int(rng.choice(len(options), p=list(TEMPERAMENT_P.values())))]
    if pick == Temperament.HOT_HEADED and hot_so_far >= MAX_HOT_HEADED:
        return Temperament.NORMAL
    return pick


def _draw_name(rng: np.random.Generator, nat: Nationality, used_surnames: set[str], team_first_names: set[str],
               star: bool, blocklist: tuple[set[str], set[str]]) -> tuple[str, str]:
    firsts, lasts = FIRST_NAMES[nat], SURNAMES[nat]
    for _ in range(500):
        first = firsts[int(rng.integers(0, len(firsts)))]
        last = lasts[int(rng.integers(0, len(lasts)))]
        if (_fold(last) in used_surnames or _fold(first) in team_first_names or _fold(first) == _fold(last)
                or is_blocked(first, last, blocklist) or (star and not is_star_surname(last))):
            continue
        return first, last
    raise RuntimeError(f"no valid name left for {nat.value}")


def _attempt(world_seed: int, attempt: int, blocklist: tuple[set[str], set[str]]) -> World:
    rng = np.random.default_rng([world_seed, attempt])
    used_surnames: set[str] = set()
    teams = []
    for tdef in TEAM_DEFS:
        slots = sorted(FORMATION_SLOTS[tdef["formation"]].items())
        drafts = [_Draft(tdef["id"], n, slot, pos, rng) for n, (slot, pos) in slots]
        offset = _solve_team(drafts, tdef["target_ovr"])
        nationalities = _draw_nationalities(rng)
        team_first_names: set[str] = set()
        hot = 0
        # The star is named first so they get the pick of the short surnames.
        order = sorted(range(11), key=lambda i: (not drafts[i].is_star, i))
        names: dict[int, tuple[str, str]] = {}
        for i in order:
            first, last = _draw_name(rng, nationalities[i], used_surnames, team_first_names, drafts[i].is_star, blocklist)
            used_surnames.add(_fold(last))
            team_first_names.add(_fold(first))
            names[i] = (first, last)
        players = []
        for i, d in enumerate(drafts):
            temperament = Temperament.NORMAL if d.is_star else _draw_temperament(rng, hot)
            hot += temperament == Temperament.HOT_HEADED
            first, last = names[i]
            attrs = d.attributes(offset)
            players.append(Player(
                id=d.id, team=d.team, name=f"{first[0]}. {last}", first_name=first, nationality=nationalities[i],
                number=d.number, position=d.position, slot=d.slot, gender=Gender.MALE, temperament=temperament,
                attributes=Attributes(**attrs), ovr=d.ovr(offset),
            ))
        teams.append(Team(id=tdef["id"], name=tdef["name"], abbr=tdef["abbr"], formation=tdef["formation"],
                          color=tdef["color"], keeper_color=tdef["keeper_color"], players=players))
    return World(seed=world_seed, teams=teams)


def roster_problems(world: World, blocklist: tuple[set[str], set[str]] | None = None) -> list[str]:
    """Every check from specs/roster-generator.md that the models do not already enforce. Empty means valid."""
    blocklist = blocklist or load_blocklist()
    problems: list[str] = []
    surnames = [_fold(p.name.split(". ", 1)[1]) for t in world.teams for p in t.players]
    if len(set(surnames)) != len(surnames):
        problems.append("two players share a surname")
    for team in world.teams:
        tdef = next(d for d in TEAM_DEFS if d["id"] == team.id)
        ovrs = [p.ovr for p in team.players]
        mean = float(np.mean(ovrs))
        if abs(mean - tdef["target_ovr"]) > TEAM_OVR_TOLERANCE:
            problems.append(f"{team.id}: mean OVR {mean:.1f} not within {TEAM_OVR_TOLERANCE} of {tdef['target_ovr']}")
        if sum(o >= 80 for o in ovrs) < MIN_STRONG[team.id]:
            problems.append(f"{team.id}: fewer than {MIN_STRONG[team.id]} players at OVR 80+")
        if float(np.std(ovrs)) < MIN_OVR_SD:
            problems.append(f"{team.id}: OVR spread {np.std(ovrs):.1f} below {MIN_OVR_SD}")
        firsts = [_fold(p.first_name) for p in team.players]
        if len(set(firsts)) != len(firsts):
            problems.append(f"{team.id}: two players share a first name")
        nats = [p.nationality for p in team.players]
        if len(set(nats)) < 3 or max(nats.count(n) for n in set(nats)) > 4:
            problems.append(f"{team.id}: nationality mix rule broken")
        for p in team.players:
            last = p.name.split(". ", 1)[1]
            if is_blocked(p.first_name, last, blocklist):
                problems.append(f"{p.id}: {p.first_name} {last} is on the blocklist")
            if _fold(p.first_name) == _fold(last):
                problems.append(f"{p.id}: first name equals surname")
            if p.id == STAR_ID:
                if p.attributes.model_dump(exclude_none=True) != STAR_ATTRIBUTES or p.ovr != STAR_OVR:
                    problems.append("star attributes or OVR differ from the hand-set values")
                if not is_star_surname(last):
                    problems.append("star surname is not short and easy to say")
                if p.temperament != Temperament.NORMAL:
                    problems.append("star must be temperament normal")
            else:
                if p.ovr > NON_STAR_OVR_CAP:
                    problems.append(f"{p.id}: OVR {p.ovr} above the non-star cap")
                if p.attributes.set_pieces > SET_PIECES_CAP:
                    problems.append(f"{p.id}: Set pieces above {SET_PIECES_CAP}")
    return problems


def generate_world(world_seed: int = WORLD_SEED) -> World:
    """Build a world that passes every roster check. Deterministic: retries use sub-seeds (seed, attempt)."""
    blocklist = load_blocklist()
    last: list[str] = []
    for attempt in range(MAX_ATTEMPTS):
        world = _attempt(world_seed, attempt, blocklist)
        last = roster_problems(world, blocklist)
        if not last:
            return world
    raise RuntimeError(f"no valid roster after {MAX_ATTEMPTS} attempts: {last}")


def world_json(world: World) -> str:
    """Canonical serialization (stable key order, UTF-8 names, trailing newline)."""
    return json.dumps(world.model_dump(mode="json", exclude_none=True), indent=2, ensure_ascii=False) + "\n"


def main() -> None:
    import jsonschema

    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--seed", type=int, default=WORLD_SEED)
    parser.add_argument("--out", type=Path, default=WORLD_PATH)
    args = parser.parse_args()

    world = generate_world(args.seed)
    text = world_json(world)
    schema = json.loads((ROOT / "contracts" / "world.schema.json").read_text(encoding="utf-8"))
    jsonschema.validate(json.loads(text), schema)  # shape
    World.model_validate_json(text)  # model-level roster rules
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(text, encoding="utf-8")
    print(f"wrote {args.out.relative_to(ROOT)}")
    for team in world.teams:
        ovrs = [p.ovr for p in team.players]
        print(f"  {team.abbr}: mean OVR {np.mean(ovrs):.1f}, range {min(ovrs)}-{max(ovrs)}")
        for p in team.players:
            print(f"    #{p.number:<2} {p.slot:<3} {p.name:<22} {p.nationality.value:<12} OVR {p.ovr}  {p.temperament.value}")


if __name__ == "__main__":
    main()
