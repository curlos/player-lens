# Phase 1 handoff: Match Data (done Oct 26, 2026)

> Short orientation notes for the next phase's session: what exists, where, and what not to break. This is a summary, not a substitute: still read CLAUDE.md, PRODUCT.md, ARCHITECTURE.md, TASKS.md, `docs/decisions.md`, the specs your phase prompt lists, and the `docs/ui/` images. The specs win over this file.

## What was built

| Piece | Where |
| --- | --- |
| Data models + JSON contracts | `sim/models.py` (world, meta, events, ratings, positions), `agents/models.py` (CommentaryChunk, CommentaryLine, ChunkPreparing, Trace), exported to `contracts/` by `scripts/export_schemas.py` |
| Roster (22 fictional players) | `sim/roster.py`, `sim/names.py`, `sim/blocklist.txt` -> `data/world.json` |
| Simulator | `sim/movement.py` (`move_player()`, the only position writer), `sim/possession.py`, `sim/rules.py`, `sim/engine.py`; every knob in `sim/config.py` |
| Off-ball detection + rating engine | `rating/offball.py`, `rating/engine.py`; knobs in `rating/config.py` |
| Spells (5-minute "control / high press / end to end / even" labels) | `rating/spells.py`, `compute_spells(events)`, events only, not written to files |
| Match files + validation | `sim/pipeline.py`, `sim/validate.py`, `sim/run.py`, `sim/library.py` -> `data/matches/<id>/{meta,events,ratings,positions}.json` |
| Calibration + seed search | `scripts/calibrate.py` (report in `docs/validation-report.md`), `scripts/find_seeds.py` |
| Dev match viewer (not the product UI) | `scripts/viewer.html` |
| Tests (68, all passing) | `tests/` |

## Key facts

- **Star / default player:** `azc_09` G. Lima (Gabriel, Brazil, ST, OVR 91). The mockups' "R. Valdemar" was a placeholder.
- **Hero match** `md38_title_decider` (seed 9447): AZC 3-2. Goals 12' Ribeiro (RDM), 39' Lima, 55' Thomas (penalty), 88' Ribeiro, 89' Lima (winner). Azure's J. Pereira sent off at 51' (second yellow). Lima finishes 8.9.
- **Library:** hero, `md19_blowout` (seed 3269, 4-0), `md27_draw` (seed 115, 1-1). Listed in `sim/library.py` `LIBRARY`.
- **Backup hero** `md38_title_decider_backup` (seed 2378, AZC 3-2, 83' penalty winner) is in `BACKUPS`: built and tested, never shown in the picker or GET /matches.
- **Calibration:** all 8 Premier League benchmark bands in over 200 seeds (passes, completion, shots, on target, goals, pressures, distance, fouls). Azure win about 58%.
- **Same seed = byte-identical files** (tested). Verified on macOS only; Phase 4 runs the tests in the linux/amd64 container.

## Rules for later phases

- **The match data is frozen.** Don't change `sim/`: any change alters every match and the library seeds (re-searching a hero takes about an hour). Rating-only changes (`rating/`) keep the matches but change `ratings.json`, so they must happen before commentary is pre-generated; regenerate with `python -m sim.run --library`.
- **Never compute numbers in the frontend or an LLM** that the files already have: ratings, importance, xG, spells.
- The four-file contract is fixed (`specs/match-files.md`); add fields only as optional and re-export the contracts.

## Data traps

- `positions.json`: integer decimeters in flat arrays (`xy[2i]`, `xy[2i+1]` = second i; divide by 10). `act` indexes `meta.activities`; the ball has no `act`. 24 entities in `meta.entity_order`.
- A goal is two events at the same `t`: a `shot` (outcome `goal`, has `speed_kmh`) and a `goal` (assister in `other`). The score field already includes the goal on both.
- About half of `events.json` is `shape_check` (importance 0.02): never show it. Rating entries with `delta` 0 (`shape_no_change`) are silent.
- `ratings.json` stores `reason_code` + `values`, never text. The 34 codes and their values are in `specs/frontend.md` ("Rating log reason text").
- `related` (optional) links an event to its causes (a goal's shot and key pass, a regain's pressure).
- Event labels use the football minute `floor(t / 60) + 1` (87:12 is 88'). No stoppage time: the match ends at 90:00.
- A sent-off player walks to the bottom touchline (activity `sent_off`) and stays there; the frontend fades the dot out.

## Accepted limitations (owner, Oct 26)

- Ratings run slightly high (mean about 7.0 vs about 6.7 on real sites).
- Too many duels (a striker can have about 20 dribbles a match); repeat decay keeps the rating effect small.
- About 4 corners a match (real about 10), a few too many offsides, few throw-ins. Not benchmark rows.

## How to run

```bash
source .venv/bin/activate
pytest                                   # 68 tests
python -m sim.run --library              # rebuild the 4 match folders (byte-identical)
python -m http.server 8000               # then open http://localhost:8000/scripts/viewer.html
```

Node is installed via nvm but is not on Claude Code's default PATH: run `source ~/.nvm/nvm.sh && nvm use 22` before npm commands.

## Open items handed on

- Owner: scan the 22 player names by eye for real players.
- Phase 3: per-agent models in `agents/models.py`; spells are ready via `rating/spells.py`.
- Phase 4: run pytest inside the linux/amd64 image (determinism check).
