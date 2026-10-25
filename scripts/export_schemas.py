"""Generate the JSON contracts in contracts/ from the Pydantic models.

Run from the repo root:  python scripts/export_schemas.py
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from sim.models import World  # noqa: E402

CONTRACTS = {
    "world.schema.json": World,
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
