# Player Lens

A live 2D synthetic football match where you follow one player: a personal AI commentator and a self-explaining rating that credits off-ball work. Built for the Microsoft x Premier League "Inside the Game" developer hackathon.

All clubs and players are fictional (Atlas League: Azure City vs Redmond United).

Status: Phase 1 (match data) built: roster, simulator, rating engine, three library matches. Agents, backend and frontend come next. Hackathon rules: see the official rules on the event site. See `PRODUCT.md`, `ARCHITECTURE.md`, `TASKS.md`, and `specs/`.

## Quick start

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill in keys; never commit .env
pytest
```

## Generate the match data (code only, no LLM calls)

Everything is seeded and deterministic: the same seed gives byte-identical files.

```bash
python scripts/export_schemas.py      # Pydantic models -> contracts/*.schema.json
python -m sim.roster                  # both squads -> data/world.json
python -m sim.run --library           # the 3 library matches (+ the backup hero) -> data/matches/<match_id>/{meta,events,ratings,positions}.json
python -m sim.run --seed 123 --match-id test   # any other seed (validation only)
python scripts/calibrate.py --seeds 200 --report docs/validation-report.md   # benchmark check
python scripts/find_seeds.py --seeds 4000      # how the library seeds were found
```

Every match file is validated against its contract and the cross-file checks in `specs/match-files.md` before it is written.

| Piece | Code |
| --- | --- |
| Data models and contracts | `sim/models.py`, `agents/models.py`, `contracts/` |
| Roster generator | `sim/roster.py`, `sim/names.py`, `sim/blocklist.txt` |
| Simulator (movement, decisions, rules, engine) | `sim/movement.py`, `sim/possession.py`, `sim/rules.py`, `sim/engine.py`, knobs in `sim/config.py` |
| Off-ball detection and rating engine | `rating/offball.py`, `rating/engine.py`, knobs in `rating/config.py` |
| Match files and validation | `sim/pipeline.py`, `sim/validate.py`, `sim/run.py`, `sim/library.py` |
| Calibration | `scripts/calibrate.py`, `docs/validation-report.md` |
| Dev match viewer (not the product UI) | `scripts/viewer.html`: run `python -m http.server 8000`, open http://localhost:8000/scripts/viewer.html |
