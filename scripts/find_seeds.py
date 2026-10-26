"""Seed search for the match library (PRODUCT, "The hero match"). The 3-2 is found, never forced.

Run from the repo root:
  python scripts/find_seeds.py --seeds 4000              # simulate seeds 1-4000 (skips ones already cached)
  python scripts/find_seeds.py --start 4001 --seeds 8000
  python scripts/find_seeds.py --cached                  # no simulation: re-filter every cached seed

Every simulated seed is summarized as one JSON line in data/seed_search.jsonl (gitignored), so a new
scenario is a quick filter instead of another hour of simulating. Each line carries a fingerprint of
data/world.json and sim/*.py; lines from an older simulator or roster are ignored and the file is rebuilt.

Criteria:
- hero (md38): Azure win 3-2, the star (azc_09) scores exactly 2, no injuries, totals near the
  benchmark means; preferred: Azure's winner comes late (story).
- hero_late (md38, owner request Oct 26): a hero match that is 2-2 until the star scores the winner
  at 85:00 or later (the last goal of the match).
- blowout (md19): Azure win 4-0 or 5-0, totals near the means.
- draw (md27): 1-1, totals near the means; preferred: a red card.
Prints the best candidates; copy the chosen seeds into sim/library.py.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from multiprocessing import Pool
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from sim.engine import simulate  # noqa: E402
from sim.models import load_world  # noqa: E402
from sim.stats import match_stats  # noqa: E402

CACHE = ROOT / "data" / "seed_search.jsonl"
STAR = "azc_09"
MEANS = {"passes": 895, "pass_completion": 0.83, "shots": 23.5, "shots_on_target": 9, "fouls_per_team": 11,
         "pressures_per_team": 145}
SCALE = {"passes": 45, "pass_completion": 0.01, "shots": 2.5, "shots_on_target": 2, "fouls_per_team": 2,
         "pressures_per_team": 30}
LATE_WINNER_T = 85 * 60
PROGRESS_EVERY = 500
_WORLD = None


def fingerprint() -> str:
    """Hash of everything that decides a match: the roster file and the simulator source."""
    h = hashlib.sha256((ROOT / "data" / "world.json").read_bytes())
    for path in sorted((ROOT / "sim").glob("*.py")):
        h.update(path.name.encode())
        h.update(path.read_bytes())
    return h.hexdigest()[:16]


def _run(seed: int) -> dict:
    """Simulate one seed and return its one-line summary."""
    global _WORLD
    if _WORLD is None:
        _WORLD = load_world(ROOT / "data" / "world.json")
    r = simulate(_WORLD, seed)
    s = match_stats(r.events, r.xy, r.sent_off)
    keep = ("score", "passes", "pass_completion", "shots", "shots_on_target", "goals", "xg", "pressures_per_team",
            "fouls_per_team", "yellows", "reds", "penalties", "offsides", "corners", "injuries", "distance_km")
    out = {k: (round(s[k], 4) if isinstance(s[k], float) else s[k]) for k in keep}
    out["seed"] = seed
    out["goal_times"] = [(e["t"], e["team"], e["player"]) for e in r.events if e["type"] == "goal"]
    out["cards"] = [(e["t"], e["team"], e["player"], e["type"]) for e in r.events if e["type"] in ("card_yellow", "card_red")]
    out["scorers"] = [g[2] for g in out["goal_times"]]
    return out


def load_cache(fp: str) -> dict[int, dict]:
    """Cached summaries for this fingerprint; a stale file (older simulator or roster) is discarded."""
    if not CACHE.exists():
        return {}
    rows, stale = {}, 0
    for line in CACHE.read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        if row.get("fp") == fp:
            rows[row["seed"]] = row
        else:
            stale += 1
    if stale:
        print(f"discarding {stale} cached seeds from an older simulator or roster")
        CACHE.write_text("".join(json.dumps(r) + "\n" for r in rows.values()), encoding="utf-8")
    return rows


def distance(s: dict) -> float:
    """How far a match's totals sit from the benchmark means (0 = exactly on them)."""
    return sum(((s[k] - MEANS[k]) / SCALE[k]) ** 2 for k in MEANS) ** 0.5


def classify(s: dict) -> str | None:
    a, r = s["score"]["azc"], s["score"]["rdm"]
    if (a, r) == (3, 2) and s["scorers"].count(STAR) == 2 and s["injuries"] == 0:
        t, team, scorer = s["goal_times"][-1]
        if team == "azc" and scorer == STAR and t >= LATE_WINNER_T:
            return "hero_late"
        return "hero"
    if r == 0 and a in (4, 5):
        return "blowout"
    if (a, r) == (1, 1):
        return "draw"
    return None


def story_bonus(kind: str, s: dict) -> float:
    if kind == "hero_late":
        return -0.5 * (s["goal_times"][-1][0] - LATE_WINNER_T) / 300  # the later the better
    if kind == "hero":
        azc_goals = [t for t, team, _p in s["goal_times"] if team == "azc"]
        return -0.5 if azc_goals and azc_goals[-1] >= 4500 else 0.0  # late winner
    if kind == "draw":
        return -0.5 if s["reds"] else 0.0
    return 0.0


def simulate_missing(seeds: list[int], cache: dict[int, dict], fp: str) -> None:
    """Simulate seeds not yet cached, appending each summary to the cache file as it finishes."""
    todo = [s for s in seeds if s not in cache]
    print(f"{len(seeds) - len(todo)} of {len(seeds)} seeds already cached; simulating {len(todo)}")
    if not todo:
        return
    start, found = time.time(), 0
    with Pool() as pool, CACHE.open("a", encoding="utf-8") as fh:
        for i, row in enumerate(pool.imap_unordered(_run, todo, chunksize=8), 1):
            row["fp"] = fp
            cache[row["seed"]] = row
            fh.write(json.dumps(row) + "\n")
            fh.flush()
            found += classify(row) in ("hero", "hero_late")
            if i % PROGRESS_EVERY == 0 or i == len(todo):
                rate = i / (time.time() - start)
                print(f"  {i} / {len(todo)} seeds, {rate:.1f}/s, about {(len(todo) - i) / rate / 60:.0f} min left, "
                      f"{found} hero candidates so far", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--seeds", type=int, default=4000)
    parser.add_argument("--start", type=int, default=1)
    parser.add_argument("--top", type=int, default=5)
    parser.add_argument("--cached", action="store_true", help="no simulation: filter every cached seed")
    args = parser.parse_args()
    fp = fingerprint()
    cache = load_cache(fp)
    if args.cached:
        pool = list(cache.values())
    else:
        seeds = list(range(args.start, args.start + args.seeds))
        simulate_missing(seeds, cache, fp)
        pool = [cache[s] for s in seeds]
    found: dict[str, list[tuple[float, dict]]] = {"hero_late": [], "hero": [], "blowout": [], "draw": []}
    for s in pool:
        kind = classify(s)
        if kind:
            found[kind].append((distance(s) + story_bonus(kind, s), s))
    for kind, items in found.items():
        print(f"\n{kind}: {len(items)} candidates in {len(pool)} seeds")
        for score, s in sorted(items, key=lambda x: (x[0], x[1]["seed"]))[: args.top]:
            goals = ", ".join(f"{int(t) // 60 + 1}' {p}" for t, _team, p in s["goal_times"])
            print(f"  seed {s['seed']:>5}  fit {score:5.2f}  passes {s['passes']}  comp {s['pass_completion'] * 100:.1f}%  "
                  f"shots {s['shots']} ({s['shots_on_target']} on)  fouls/team {s['fouls_per_team']:.1f}  "
                  f"reds {s['reds']}  [{goals}]")


if __name__ == "__main__":
    main()
