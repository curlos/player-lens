# Player Lens

A live 2D synthetic football match where you follow one player: a personal AI commentator and a self-explaining rating that credits off-ball work. Built for the Microsoft x Premier League "Inside the Game" developer hackathon.

All clubs and players are fictional (Atlas League: Azure City vs Redmond United).

Status: Phase 1 (match data) and Phase 2 (match viewer, `web/`) built. Commentary is a code-built template placeholder until the agent pipeline and backend (Phase 3) land. Hackathon rules: see the official rules on the event site. See `PRODUCT.md`, `ARCHITECTURE.md`, `TASKS.md`, and `specs/`.

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

## Run the match viewer (web/)

React + Vite + Tailwind + TypeScript. Needs Node 20+ (the dev machine uses `source ~/.nvm/nvm.sh && nvm use 22`). The dev server reads the match files straight from `data/matches/`; nothing is copied into `web/`.

```bash
cd web
npm install
npm run dev          # http://localhost:5173 (opens on the hero match with a Start overlay)
npm test             # unit tests for the pure helpers (formatters, reason templates, lookups, template commentary)
npm run build        # typecheck + production build into web/dist (served by FastAPI from Phase 4)
npm run gen:types    # regenerate src/types/generated/ after contracts/*.schema.json change
```

Keyboard: Space plays or pauses (and starts from the overlay), Enter starts, left and right arrows seek 5 s.

| Piece | Code |
| --- | --- |
| Data loading and lookups | `web/src/lib/match.ts` |
| Playback clock | `web/src/lib/clock.ts`, `web/src/hooks/useClock.ts` |
| Rating reason templates (EN/ES) | `web/src/lib/reasons.ts` |
| Commentary placeholder (`getCommentaryChunk`, `getTrace`) | `web/src/lib/commentary.ts` |
| Audio hooks (no-op until Phase 3) | `web/src/lib/audio.ts` |
| Frontend knobs | `web/src/lib/config.ts` |
| Components (pitch, panels, overlays) | `web/src/components/` |
| Dev data serving (`/data`, `GET /matches`) | `web/scripts/match-data-plugin.ts` |
