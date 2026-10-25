# Player Lens

A live 2D synthetic football match where you follow one player: a personal AI commentator and a self-explaining rating that credits off-ball work. Built for the Microsoft x Premier League "Inside the Game" developer hackathon.

All clubs and players are fictional (Atlas League: Azure City vs Redmond United).

Status: planning docs complete, build starting. Hackathon rules: see the official rules on the event site. See `PRODUCT.md`, `ARCHITECTURE.md`, `TASKS.md`, and `specs/`.

## Quick start (once built)

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill in keys; never commit .env
python scripts/export_schemas.py
pytest
```
