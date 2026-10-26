# TASKS: Player Lens

> Major tasks only. Break each into smaller steps in plan mode. Read CLAUDE, PRODUCT and ARCHITECTURE first.

## Deadlines

- **Submission target: Tue Oct 27, 2026, 6:00 PM ET (3:00 PM PT).**
- **Official cutoff: Tue Oct 27, 11:59 PM PT = Wed Oct 28, 2:59 AM ET.**
- Live link must stay up through Nov 10.

## Done

- [x] Scope locked (PRODUCT)
- [x] Tech stack and design (ARCHITECTURE)
- [x] Rules for coding agents (CLAUDE)
- [x] World data models: `sim/models.py` (Player, Team, World per specs/roster-generator.md) and the generated `contracts/world.schema.json`
- [x] All planning docs written and reviewed: PRODUCT, ARCHITECTURE, CLAUDE, and the nine specs in `specs/`; research and decisions in `docs/`
- [x] Research on attribute models and simulator calibration
- [x] Gemini UI mockups for all 11 screens (approved; style reference only; images in `docs/ui/`)
- [x] Match library decided: three matches (hero 3-2, blowout, 1-1 draw), all Azure City vs Redmond United
- [x] Phase 1 match data (Oct 25): contracts for meta, events, ratings, positions, commentary chunk and trace (`scripts/export_schemas.py`); roster generator and `data/world.json`; simulator with `move_player()`, decisions, fouls, cards, restarts and reactions; off-ball detection and rating engine; match files with validation; calibration (all 8 benchmark rows in band, `docs/validation-report.md`); hero seed search and the three library matches in `data/matches/` (hero seed 9447: 2-2 until Lima's 89' winner; backup hero seed 2378). Added Oct 26: spells (`rating/spells.py`) and the Phase 2 input reference in `specs/agents-backend.md`. Tests for each piece. Choices logged in `docs/decisions.md`.

## Remaining major tasks

1. ~~**Contracts:** generate the remaining JSON schemas from the Pydantic models (events, ratings, positions, meta, commentary) per `specs/match-files.md`.~~ Done Oct 25 (per-agent contracts are added with the agent pipeline).
2. **Setup:** public GitHub repo, Azure free account (sign up early so the $200 credit covers judging), Foundry model deployed with a 10-line smoke test, $5 budget alert, CodeRabbit installed on the repo.
3. ~~**World data:** roster generator (archetype baseline + seeded noise, unique shirt numbers, fictional names, famous-player blocklist check, gender field default `male`) that writes `data/world.json` with both teams filled.~~ Done Oct 25. Owner: scan the 22 names by eye.
4. ~~**Match simulator:** movement via `move_player()`, events, fatigue, writes `meta`, `events`, `ratings`, `positions` JSON per match, validation report against the benchmark table, hero seed search (Azure wins 3-2, star scores twice).~~ Done Oct 25.
5. ~~**Rating engine:** deltas, repeat decay, soft cap, reason log, off-ball detection.~~ Done Oct 25; tuning closed Oct 26 (values accepted as is).
6. **Agent pipeline:** agents on Microsoft Agent Framework, contract validation at each handoff, 1-minute commentary chunks with caching, Fact Guard, Voice Director.
7. **Backend API:** FastAPI serving static match files and commentary chunks (no SSE).
8. **Frontend:** Start match overlay, SVG pitch, spotlight, player card, commentary panel with "How this was made", All ratings lineup, auto-hiding control bar, View popover.
9. **Personalization:** Casual/Analyst modes, English/Spanish.
10. **Testing and evals:** simulator invariant tests, rating sum test, match-file validation, Fact Guard validator tests, backend endpoint tests with mocked LLM (no live calls), LLM fact-check evals. **Write alongside each piece and run after every change (approved Oct 25).**
11. **Deployment:** Azure Container Apps plus saved-replay fallback.
12. **Submission package:** README, architecture diagram, demo video under 2 minutes, pitch text, submission form.

## Schedule

- **Sun Oct 25:** repo setup, roster generator, simulator, rating engine, match files.
- **Mon Oct 26:** frontend, agent pipeline and backend, deploy.
- **Tue Oct 27:** demo video, README, end-to-end test of the live link, fixes, submit by 6:00 PM ET.

(Keep testing alongside each piece.)

## Cut order if behind

Extra matches, then league table, then Spanish, then recaps, then Analyst mode.

**Never cut:** the rating reason log and the "How this was made" trace.

## Open decisions (owner must answer; don't guess)

- [x] Extra attributes: done (12 outfield plus Shot-stopping for GKs); `sim/models.py` updated.
- [x] Agent roster: confirmed Oct 24. Personalizer is a separate agent (Interpreter, Moments, Commentator, Fact Guard, Personalizer, Voice Director).
- [x] Commentary cadence: decided Oct 24. At least 5 s and at most 15 s between lines (end of clip to start of the next); big moments may interrupt the minimum.
- [x] Rating deltas: Closed Oct 26 (owner): first-pass values kept as final for the hackathon; see docs/decisions.md.
- [x] Redmond formation: 4-4-2.

## Decisions already made

- League: Atlas League. Teams: Azure City (AZC, blue, 4-3-3, high press) and Redmond United (RDM, red, 4-4-2, deeper block).
- Mixed nationalities in the roster names; all fictional; all players male for now (gender field default `male`), user-facing copy gender-neutral.
- 2D dots, not 3D. Python simulator, seeded and deterministic, run offline. JSON files, no database.
- The browser downloads four static files per match and plays them back locally; commentary streams in 1-minute chunks, cached; hero match and default star pre-generated.
- Small OpenAI model on Foundry (Azure free credit); Claude in Foundry is skipped (needs pay-as-you-go).
- Deploy as one Docker container on Azure Container Apps.
- Tests are required for the deterministic parts (decided Oct 25), none for React components. CodeRabbit reviews the repo.

## Known stale items

- `docs/project-summary.md` still says AZU/CRC and a noon PT target; PRODUCT overrides it (AZC/RDM, 6 PM ET).
- `docs/ui/` images are style references only; PRODUCT and the specs win on any conflict (for example screen 9 shows many players outside the box; the real rule is only taker and keeper inside).

## Known gaps

- The challenge brief was reviewed Oct 24 (five-stage pipeline, synchronized overlays, recaps, multi-language); its requirements are folded into PRODUCT. Still glance at the website's Challenge page for any event-format details before finalizing the simulator's output.
- Not done yet: Azure free account sign-up, Foundry smoke test, $5 budget alert, public GitHub repo.
- Roster generator must include the real-player name blocklist check.
- Why we chose things: see the Decisions log doc.
