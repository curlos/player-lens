# CLAUDE.md: Rules for coding agents on Player Lens

> Read PRODUCT (what and why) and ARCHITECTURE (how) before changing anything. If code and docs disagree, stop and flag it; don't silently pick one.

## Project in one line

Live 2D synthetic football match. Click any player for a personal commentator and a self-explaining rating that credits off-ball work. Hackathon entry; solo developer; deadline is tight, so finishable beats perfect.

## Hard rules

1. **Code computes every number. The LLM only writes words.** Never let a model produce stats, ratings or coordinates.
2. **Fictional world only.** No real clubs, players, leagues, logos or footage. Teams: Azure City (AZC) and Redmond United (RDM), Atlas League. Check any new player name against well-known real players.
3. **Never use EA's data, real player ratings or EA-branded terms** (say "Traits", not "PlayStyles").
4. **No Azure or Microsoft logos or product styling in the UI.** "Azure" is only a club and color name.
5. **Determinism:** same seed gives identical output. Use one seeded RNG passed explicitly. No `random` module globals, no wall-clock time in the simulator.
6. **Positions change in one place only**, `move_player()`. Speed capped (about 9 m/s), no teleporting, everything stays in the pitch.
7. **Units are meters.** Pitch 105 x 68, origin top-left, x along length, y across width. The frontend uses `viewBox="0 0 105 68"`.
8. **Every event has a unique ID.** Player IDs are `team_NN`, e.g. `azc_09`.
9. **Validate at every handoff.** Each agent's output is checked against its schema in `contracts/` before the next step.
10. **The replay never waits on an AI call.**
11. **No secrets in the repo.** Keys come from environment variables; `.env` is gitignored. Never commit keys, never print them.
12. Do not call a live LLM from tests or validation runs. LLM calls happen in the offline pre-generation step (hero match and default star) and, for anonymous visitors, only for uncached commentary chunks under the daily spend cap (env var, starts at 0). Everything is cached by (match, player, mode, language, chunk).
13. **Scope is final.** Don't add 3D, substitutions, a database, accounts or extra features. Cut order if behind: extra matches, league table, Spanish, recaps, Analyst mode. Never cut the rating reason log or the "How this was made" trace.
14. Never run git commit, git push, or open PRs. Leave all changes uncommitted; the developer reviews the diff and commits.

## Stack

- Backend: Python 3.11+, numpy, Pydantic (models and JSON schema), FastAPI serving static match files and commentary chunks (no SSE).
- Agents: Microsoft Agent Framework (Python), model hosted on Microsoft Foundry (small OpenAI model).
- Frontend: React + Vite + Tailwind, functional components and hooks, SVG pitch.
- Storage: plain JSON files (`meta`, `events`, `ratings`, `positions` per match).
- Deploy: one Docker container on Azure Container Apps, plus a saved-replay fallback.

## Working style

- **Use plan mode before each task.** State the plan, then build.
- Spec first: write or update the relevant file in `specs/` and `contracts/` before code.
- Small, reviewable changes. Name things clearly; keep structure obvious.
- Document public functions briefly. Judges score code quality and documentation.
- Prefer deterministic code over LLM calls wherever either would work.
- When something is a guess (formulas, rating deltas, probabilities), say so in a comment and keep the knob in one config place so it can be tuned.
- Write tests alongside each piece and run them after every change: simulator invariants (speed cap, pitch bounds, determinism, unique ids, 11 players, goals equal score), rating sum, match-file validation, Fact Guard validator, and backend endpoints with mocked LLM calls (no live calls). No tests for React components or exact commentary text.

## Definition of done for a task

- Matches the relevant spec and contract.
- Runs from a clean clone with documented commands.
- No keys, no real names, no copied branding.
- README or spec updated if behavior changed. Tests pass.

## Key facts to not get wrong

- Rating starts at 6.0; soft cap, range 3.1 to 9.9 shown to one decimal; no provisional period.
- Off-ball definitions: counterpress = pressure within 5 s of our own turnover; pressure regain = ball won back within 5 s of that pressure.
- Targets per match (for calibration): passes 850-940, completion 82-84%, shots 22-25, goals 2.5-3.0.
- Azure attacks left to right all match (no halftime side switch). Three matches, all Azure City vs Redmond United.
- Submission target: Tue Oct 27, 2026, 6:00 PM ET. Official cutoff: Wed Oct 28, 2:59 AM ET.

## Developer and environment notes

- Solo developer. Personal notes for the agent (if present) are in `CLAUDE.local.md`, which is not committed.
- **Build Docker images with `--platform linux/amd64`** (dev machine is Apple Silicon) or they won't run on Azure Container Apps.
- Frontend: Tailwind CSS (no named CSS classes), functional components and hooks only.
- Review style: he reviews core and critical code and relies on tests for the rest, and wants to move toward test-driven development. Make tests meaningful (the invariants in ARCHITECTURE section 3 and the checks in Spec: Match Files). CodeRabbit reviews the repo, so keep changes small with clear descriptions.
- Communication: short and concise, lead with the answer, bullets for lists, one piece at a time. If a request is ambiguous, ask one clarifying question first. Avoid walls of text.
- Extra context lives in `docs/`: `decisions.md` (why we chose things), `research-attributes-and-sim.md` (simulator formulas and benchmarks), `research-microsoft-and-cost.md` (Microsoft tech, pricing, existing simulators), `hackathon-rules.md` (local only, not committed; if missing, see the official rules on the hackathon site), `project-summary.md` (original summary; PRODUCT wins on conflicts).
- Specs live in `specs/`: `roster-generator.md`, `simulator-movement.md`, `simulator-possession.md`, `match-rules.md`, `rating-model.md`, `match-files.md`, `agents-backend.md`, `frontend.md`, `deployment.md`. Read the matching spec before building each piece. Approved UI mockups are in `docs/ui/` (style and layout references only; specs win). Environment variables are listed in `.env.example` and `specs/deployment.md`.
