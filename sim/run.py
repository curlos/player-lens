"""Simulate a match and write its four files to data/matches/<match_id>/ (specs/match-files.md).

Run from the repo root:
  python -m sim.run --library                    # build the three library matches and the backup
  python -m sim.run --seed 123 --match-id test   # one ad-hoc match

Every file is validated (contracts + cross-file checks) before anything is written; a failure aborts.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from sim.library import BACKUPS, LIBRARY
from sim.models import load_world
from sim.pipeline import MatchInfo, build_match, summary
from sim.validate import match_problems, schema_problems

ROOT = Path(__file__).resolve().parent.parent
MATCHES_DIR = ROOT / "data" / "matches"


def build_and_write(info: MatchInfo, out_root: Path = MATCHES_DIR, world_path: Path = ROOT / "data" / "world.json") -> dict:
    """Build, validate and write one match. Raises SystemExit with the problems if validation fails."""
    world = load_world(world_path)
    files = build_match(world, info)
    texts = files.texts()
    problems = schema_problems(texts) + match_problems(files.meta, files.events, files.ratings, files.positions)
    if problems:
        raise SystemExit(f"{info.match_id}: validation failed:\n  " + "\n  ".join(problems[:20]))
    out = out_root / info.match_id
    out.mkdir(parents=True, exist_ok=True)
    for name, text in texts.items():
        (out / name).write_text(text, encoding="utf-8")
    return summary(files)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--library", action="store_true", help="build every match in sim/library.py (backups too)")
    parser.add_argument("--seed", type=int)
    parser.add_argument("--match-id", default="adhoc")
    parser.add_argument("--matchday", type=int, default=1)
    args = parser.parse_args()
    infos = LIBRARY + BACKUPS if args.library else [MatchInfo(args.match_id, args.seed, f"Matchday {args.matchday}", args.matchday)]
    if not args.library and args.seed is None:
        parser.error("give --seed N or --library")
    for info in infos:
        s = build_and_write(info)
        goals = ", ".join(f"{int(t) // 60 + 1}' {p}" for t, p, _a in s["scorers"])
        print(f"{info.match_id}: seed {info.seed}  AZC {s['score']['azc']}-{s['score']['rdm']} RDM  [{goals}]  "
              f"{info.default_player} rating {s['star_rating']:.1f}")
    sys.stdout.flush()


if __name__ == "__main__":
    main()
