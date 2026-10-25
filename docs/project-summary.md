# Project Summary: Player Lens

Oct 23, 2026 · @Carlos Martinez

> **Note:** original project summary written Oct 23. Where it conflicts with PRODUCT or ARCHITECTURE, those win: teams are AZC/RDM (not AZU/CRC), the submission target is Tue Oct 27, 6:00 PM ET (not noon PT), and the attribute list is expanded. Other changes since Oct 23: SSE is gone (the browser plays four static match files locally); the "Behind the scenes" strip became a per-line "How this was made" trace; 12 attributes plus GK Shot-stopping; matches last exactly 90:00 with no stoppage time; commentary comes in 1-minute chunks, off above 1x; playback speeds are 1x, 2x, 4x, 6x, 8x and 10x; there is no provisional rating; tests are required for the deterministic parts; the Personalizer is a separate agent; the build schedule below is superseded by TASKS and the Submission Plan.

## The idea in brief

Player Lens is a live 2D football match where you click any of the 22 players and get a personal commentator and a self-explaining rating for that player. It is Carlos's entry to the Microsoft x Premier League "Inside the Game: Developer Hackathon".

The pitch in one line: pick a player, follow the match through their eyes, and see exactly why their rating moves, including the off-ball work that normal ratings ignore.

Why it exists: match ratings from WhoScored, Sofascore and FotMob are black boxes built on on-ball events, so a player who presses, tracks back and makes decoy runs gets no credit and no explanation. Player Lens credits that work and logs a reason for every change. It also tailors the commentary to the viewer (Casual or Analyst, English or Spanish).

## Hackathon context

Submissions close Tue Oct 27, 2026 at 11:59 PM PT; judging runs to Nov 10 and the top six are notified. Carlos is already registered and is eligible (not a student or employee requirement; no ties to Microsoft or the Premier League).

- **Task:** build a five-stage pipeline: ingest, interpret, explain, render, personalize.
- **Data:** synthetic only. Fictional league, clubs and players; no real clubs, trademarks or footage.
- **Judging (5 x 20%):** technological implementation, agentic design, real-world impact, UX and presentation, category adherence.
- **Hero technologies:** Microsoft Foundry, Agent Framework, Azure MCP, GitHub Copilot Agent Mode, Azure Container Apps.
- **Deliverables:** public GitHub repo, demo video under 2 minutes, live link kept up through Nov 10.
- **Prizes:** Grand Prize (1st and 2nd), plus category prizes: Best Use of Foundry, Best Enterprise Solution, Best Multi-Agent System, Best Azure Cloud Native Integration.
- **Credits:** Azure free account gives $200 for 30 days. Claude models in Foundry need pay-as-you-go, so use OpenAI models on the free account and set a $5 budget alert.

## Goals and prize strategy

The realistic target is Best Multi-Agent System; the Grand Prize is a long shot. The second goal is a portfolio-quality repo.

- **Why this project fits:** it shows full-stack skills, cloud deployment, AI agents, testing and system design in one repo a recruiter can open.
- **How to win the multi-agent category:** distinct agent roles, shared state and handoffs, and recovery from failure. A visible "Behind the scenes" panel proves this to judges in the demo.
- **Learning goal:** adopt a modern AI-first workflow (specs, plan mode, parallel agents, tests and evals, skills, MCP) rather than just prompting.

## Product features

| Feature | What it does |
| --- | --- |
| Live synthetic match | 2D pitch, 22 dots, ball, score bar and clock, replayed from simulator output |
| Player spotlight | Click any player: lime ring on that dot, everyone else dims, one fading trail |
| Live rating | Starts at 6.0 and changes with every action; each change logs a reason |
| Off-ball credit | Pressure regains, recovery runs, marking denial and decoy runs score; so do negatives like losing the ball or not tracking back |
| Personalized commentary | AI feed for the selected player; Casual or Analyst mode; English or Spanish |
| Recaps | Player recap at halftime and full time |
| All ratings view | Ratings for all 22 players, always computed by code |
| Behind the scenes | Panel showing the agents working, including Fact Guard fixes |

## Multi-agent design

Six agents split the work, each with one job. Code computes the numbers; the agents interpret facts and write words. This is how Player Lens answers the category's test: distinct roles, shared state and handoffs, and recovery from failure.

Each agent reads the previous one's output and writes its own, so a judge can follow one moment from raw event to finished line.

- **Shared state:** the event log and the rating log, passed between agents as JSON that follows the contracts.
- **Handoffs:** each agent's output is validated against its contract before the next one starts.
- **Recovery:** Fact Guard fixes or removes any claim the event log does not support; the Behind the scenes panel shows each fix.
- **Timing:** fast deterministic steps run in sequence; slow AI steps run async and in parallel.
- **Cost:** AI runs only for the selected player, and results are cached by (moment, player, mode, language).

## UI and visual design

The UI is a 2D dots-on-a-pitch view, not 3D. It is cheaper, more reliable in 3.5 days, and the value is in the data and explanations, not the graphics. A "studio" feel comes from clean overlays, not player models.

- **Pitch:** medium, desaturated green so the dots and overlays stand out.
- **Selection:** lime ring around the selected dot; no ground ring.
- **Spotlight mode:** dims everyone else; the normal view dims no one.
- One fading trail for the selected player only.
- Brief fading action visuals: pass line, shot line with a speed pop, tackle flash, pressure pulse, rating pop.
- **Layout (from the Gemini design target):** dark UI, score bar (e.g. "AZU 1 - 0 CRC 63:12"), selected-player card with rating and reason log, commentary panel, "Behind the scenes" strip, "All ratings" button.

Fixes to record in specs/frontend.md (the Gemini image had these errors, so use it for style and layout only):

- Unique shirt numbers; exactly 11 per side with visible goalkeepers.
- Consistent spotlight dimming.
- One trail and no contradictory run arrows.
- Matching team abbreviations (AZU, CRC) everywhere.
- Mode toggle and text must agree.

Save the image as docs/design-target.png. Do not copy Prime Vision (Amazon) branding; its event alerts, name tags, shot-speed pop and mini pitch are inspiration only.

## Synthetic data

The data comes from a seeded Python Monte Carlo simulator, not from an LLM. It rolls weighted dice by player attributes, like the NBA 2K engine. The same seed always gives the same match.

- **Pitch:** 105 x 68 m. Positions are recorded every second.
- **Movement:** players move toward target spots set by formation and role, capped at human speed (about 9 m/s). No teleporting; a 35 m run takes roughly 3.5 to 4 seconds.
- **Attributes (8):** Pace, Passing, Finishing, Dribbling, Defending, Positioning, Work rate, Stamina, grouped into archetypes.
- **Teams:** two detailed fictional teams, not a 20-team league.
- **Matches:** several seeded matches, plus a validation report against real averages (about 800 to 1,000 passes, 80 to 85% completion, 20 to 25 shots, 2 to 3 goals).
- **Stoppage time:** simple rule, 1 to 5 minutes.

Data shapes (positions and events as JSON):

```json
{"t": 3792, "ball": [52.1, 34.0], "players": {"AZU_6": [48.2, 30.5]}}
{"id": "ev_1843", "t": 3792, "type": "pass", "player": "AZU_6", "receiver": "AZU_9", "from": [48.2, 30.5], "to": [60.0, 28.1], "outcome": "complete", "progressive": true, "difficulty": 0.4}
{"event": "ev_1843", "t": 3792, "player": "AZU_6", "rating": [7.1, 7.2], "delta": 0.1, "reason": "Progressive pass under pressure"}
{"moment": "m_212", "player": "AZU_6", "mode": "analyst", "lang": "en", "text": "...", "fact_check": "pass"}
```

The values above are illustrative. Events carry unique IDs, because minute and second alone do not identify an event.

## Rating model

Every player starts at 6.0 and each action adds or subtracts a fixed amount. Code computes all of it; the LLM only rephrases the explanation. Real systems (WhoScored, Sofascore, FotMob) are proprietary; the public FPL bonus points system is the closest reference. They are event-based and ignore off-ball work, which is Player Lens's gap.

| Action | Delta |
| --- | --- |
| Goal | +1.0 |
| Assist | +0.6 |
| Shot on target | +0.15 |
| Tackle | +0.15 |
| Interception | +0.12 |
| Block | +0.2 |
| Pressure regain | +0.12 |
| Counterpress | +0.15 |
| Recovery run | +0.15 |
| Marking denial | +0.05 per window, capped at +0.3 |
| Decoy run | +0.1 |
| Dispossessed | -0.08 |
| Error leading to goal | -1.0 |

These are starting values and need tuning against the simulator.

- **Repeat decay:** the same action earns less each time.
- **Soft cap:** ratings flatten near the top so they stay between about 3 and 10.
- **Provisional:** a rating is marked provisional until about 10 minutes are played.
- **Explanations:** deterministic templates first; an optional LLM rephrase second.
- **Cadence (tentative):** ratings update on every event; commentary has a minimum gap of about 10 to 15 seconds and at most about 60 seconds of silence. The research on commentary pacing is not yet reviewed, so this is not final.

## AI and cost strategy

The rule: code computes every number; the LLM only writes words. That keeps costs low and stops the AI inventing stats.

- **Cheap by design:** ratings for all 22 players are always computed by code. AI commentary runs only for the selected player.
- **Caching:** cache AI output by (moment, player, mode, language) so repeat views cost nothing.
- **Models:** small OpenAI models on the free Azure account (the $200 credit lasts 30 days). Claude in Foundry needs pay-as-you-go, so skip it. Set a $5 budget alert.
- **Never block the match:** the replay runs on its own clock and never waits for an AI call.
- **Fallback:** keep a saved replay with pre-generated commentary in case the live link or credits fail during judging.
- **Demo example (not for submission):** a mini-engine for the 2017 Clasico showed event, then key moment, then grounded facts, then personalized lines. The submission must use fictional names only.

## Architecture decisions

Each decision follows the same format: options, decision, how it works, what you gave up.

| Decision | Choice | What it costs |
| --- | --- | --- |
| Dots vs 3D | 2D dots | Less visual wow; far less risk in 3.5 days |
| Who makes numbers | Code, always | LLM cannot freestyle stats; commentary feels more constrained |
| Live push | SSE for commentary and rating events | One-way only; fine because the viewer only sends clicks |
| AI work timing | Fast deterministic steps run in sequence; slow AI steps run async and in parallel | More moving parts to coordinate |
| Cache key | (moment, player, mode, language), with unique event IDs | Cache misses on the first view of each combination |
| Match clock | Replay never waits on AI | Commentary can arrive a moment late |
| Hosting | Azure Container Apps, plus a saved-replay fallback | Fallback must be kept in sync |
| Storage | Simple JSON files for matches | No database to scale; fine for a demo |

If a database is added later, MongoDB documents are capped at 16 MB, so store one document per event rather than one blob per match.

## Competitive landscape

A scan of 572 submitted projects shows the crowded themes and the gap Player Lens fills.

- **Crowded:** AI broadcast crew or director, verified or evidence-backed commentary, what-if scenarios, multilingual commentary.
- **Closest competitor:** "Shield: Play Like Your Idol".
- **Player Lens's gap:** click any player for a live commentator, a rating that explains itself, and credit for off-ball work.
- **Real-world value:** fans and FPL managers who want to follow one player; broadcasters who want player-level graphics; youth coaching that rewards work rate, not just touches.
- **Risk:** "fact-checked commentary" overlaps with the crowded themes, so lead the demo with the rating reason log and off-ball credit, not with Fact Guard.

## Workflow, testing and documents

The workflow is spec-first: write the plan in documents, then let agents build against it.

**Documents to write**

- PRODUCT.md (what and why)
- ARCHITECTURE.md (how the parts fit)
- contracts/ (JSON schemas for events, rating changes, commentary)
- CLAUDE.md or AGENTS.md (rules for the coding agent)
- TASKS.md and specs/ (world, simulator, stats, agents, api, frontend, deploy)
- TESTING.md, README and a demo script

**How to build**

- Use plan mode before each task; use git worktrees (or Superset) to run agents in parallel.
- Tests are the spec: contract tests for the JSON shapes, property-based tests for the simulator (speed limits, ball always on pitch), and evals for LLM output (no invented facts).
- Review in tiers: names and structure first, risky code second, spot-check the rest, then use the app yourself.
- Microsoft skills playlists: only a short pass is needed. About 1 hour each on Foundry, Foundry Agents and Agentic Workflows, 15 minutes on Copilot Agent Mode, and skip Data. Use them as reference when stuck, not as courses to finish first.

## Build plan, cut order and risks

About 3.5 days remain from Friday evening. Aim to submit by noon PT on Tue Oct 27 (3 PM ET), leaving a cushion before the 11:59 PM PT deadline.

1. **Fri night (about 90 min):** write PRODUCT.md; create the public repo with README stub and CLAUDE.md; run a Foundry smoke test (deploy one small model, call it from a 10-line Python script).
2. **Sat:** world file (two fictional teams, archetypes, 8 attributes); simulator with validation report; stats and rating engine with reason log. Goal by evening: a match plays as dots with live ratings.
3. **Sun:** agent pipeline with caching and the Behind the scenes panel; spotlight view, Casual and Analyst modes, English and Spanish, recaps.
4. **Mon:** deploy to Azure Container Apps with a saved-replay fallback; record the demo video (under 2 minutes); finish README and architecture diagram.
5. **Tue:** test the live link end to end and submit by noon PT.

Cut order if behind: Spanish first, then recaps, then Analyst mode. Never cut the rating reason log or the multi-agent panel; those are what win the category.

**Main risks**

- Simulator realism takes longer than planned (fallback: fewer events, simpler formations).
- Azure setup or credits fail (fallback: smoke test tonight; saved replay).
- AI latency or cost (fallback: cache and pre-generate commentary).
- Scope creep into 3D or extra features (fallback: this document's scope is final).

## Open items and next steps

- [ ] Write PRODUCT.md and lock the scope.
- [ ] Create the public GitHub repo and add CLAUDE.md.
- [ ] Run the Foundry smoke test and set the $5 budget alert.
- [ ] Save the Gemini design image as docs/design-target.png.
- [ ] Review the commentary-pacing and rating-cadence research, then finalize the cadence in the spec.
- [ ] Write ARCHITECTURE.md and the JSON contracts, then specs/world.md and specs/simulator.md.
- [ ] Tune the rating deltas against simulator output.
