"""Generate the JSON contracts in contracts/ from the Pydantic models.

Run from the repo root:  python scripts/export_schemas.py
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from agents.models import (  # noqa: E402
    CanonicalLine, ChunkPreparing, CommentaryChunk, Fact, GuardResult, Moment, Recap, Trace, Variant, VoiceDirection,
)
from sim.models import EventsFile, Meta, PositionsFile, RatingsFile, World  # noqa: E402

CONTRACTS = {
    "world.schema.json": World,
    "meta.schema.json": Meta,
    "events.schema.json": EventsFile,
    "ratings.schema.json": RatingsFile,
    "positions.schema.json": PositionsFile,
    "commentary_chunk.schema.json": CommentaryChunk,
    "commentary_preparing.schema.json": ChunkPreparing,
    "trace.schema.json": Trace,
    "fact.schema.json": Fact,
    "moment.schema.json": Moment,
    "canonical_line.schema.json": CanonicalLine,
    "guard_result.schema.json": GuardResult,
    "variant.schema.json": Variant,
    "voice_direction.schema.json": VoiceDirection,
    "recap.schema.json": Recap,
}


def main() -> None:
    out_dir = ROOT / "contracts"
    out_dir.mkdir(exist_ok=True)
    for filename, model in CONTRACTS.items():
        path = out_dir / filename
        path.write_text(json.dumps(model.model_json_schema(), indent=2) + "\n", encoding="utf-8")
        print(f"wrote {path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
