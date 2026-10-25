# ARCHITECTURE: Player Lens

Oct 24, 2026 · @Carlos Martinez

> How the parts fit. Read PRODUCT first. Contracts in `contracts/` are the source of truth for data shapes; this file explains the design around them.

## 1. System overview

```text
world.json (teams, players, attributes, formations)
        |
        v
 SIMULATOR (Python, seeded, deterministic, run offline) ---> meta.json, events.json, positions.json
        |                                       positions 1 Hz + events (unique IDs)
        v
 RATING ENGINE (code only) ---> ratings.json (one entry per rating change, with reason)
        |
        v
 AGENT PIPELINE (Microsoft Agent Framework, Foundry-hosted model)
   Interpreter -> Moments -> Commentator -> Fact Guard -> Personalizer -> Voice Director -> Azure AI Speech
        |
        v
 commentary cache (JSON + audio): hero match and default star pre-generated offline,
 other players generated on demand in 1-minute chunks under a daily spend cap
        |
        v
 FastAPI: static match files + commentary chunks  ------>  React frontend (browser plays the match back locally, SVG pitch)
        |
        v
 One Docker container on Azure Container Apps
```

Principle: **code computes every number; the LLM only writes words.** The replay runs on its own clock and never waits for an AI call.

## 2. Pitch and coordinates (single source of truth)

- Pitch is **105 m x 68 m**, units in meters.
- Origin (0, 0) is the top-left corner. x runs 0-105 along the length, y runs 0-68 across the width.
- Azure City attacks left to right for the whole match. Redmond United is mirrored. There is no halftime and no side switch.
- Formation slot coordinates are normalized 0-1 and live in the simulator config (`FORMATION_XY`), keyed by (formation, shirt number), not in `world.json` (whose `slot` is only a label like "CB", shared by both centre-backs). Convert: x = slot.x \* 105, y = slot.y \* 68. Mirror for the away side: x = 105 - slot.x \* 105, y = 68 - slot.y \* 68.
- Markings (Laws of the Game): goal 7.32 m wide; penalty area 16.5 m deep, 40.32 m wide; goal area 5.5 m deep, 18.32 m wide; penalty spot 11 m; center circle radius 9.15 m.
- Frontend draws an SVG with `viewBox="0 0 105 68"` and uses meters directly. Never convert to pixels in data code.

## 3. Simulator

### Rules that must always hold (determinism and realism invariants)

These are written as invariants now so tests can be written from them later.

1. Same seed gives byte-identical output.
2. **Players move only via one function, `move_player()`.** It moves toward a target by at most `max_speed * dt`. No other code writes positions.
3. Max speed is hard-capped at about 9 m/s; individual top speed scales with Pace and is reduced by fatigue. A 35 m run takes roughly 3.5-4 s. No teleporting.
4. Acceleration is limited per player (Acceleration attribute).
5. Players and ball stay within the pitch (ball may leave for throw-ins, corners and goal kicks as explicit events).
6. Ball speed is capped at a realistic shot speed (about 30 m/s).
7. Exactly 11 players per side, unique shirt numbers per team.
8. Every event has a **unique ID** (e.g. `ev_1843`). Time alone does not identify an event.
9. Match length: exactly 90:00 (5,400 seconds), no stoppage time.

### Model

- Positions recorded every **1 second**. The frontend interpolates between snapshots so dots glide.
- Players move toward target spots set by formation, role, ball position and team style (`press_intensity`, `tempo`, `width`, `def_line`, `style`), which lives in the simulator config keyed by team id (`TEAM_TACTICS`), not in `world.json`.
- Events are **two-step**, modeled on Football Manager: **decide** (which action or target, driven by e.g. Vision) then **execute** (does it succeed, driven by e.g. Passing, Composure). This also makes rating explanations self-describing.
- Success probabilities are logistic functions of attributes, distance and pressure. Starting formulas are guesses to be calibrated, not facts.
- Fatigue: Stamina sets how fast it builds; Work rate raises load; fatigue reduces speed and acceleration proportionally.
- Fictional world only. No real names, no EA data, no copied ratings.

### Events, activities and match rules (added in review)

- **Two code lists.** Events can change a rating: pass, key\_pass, shot, goal, save, tackle, interception, block, clearance, aerial\_duel, dribble, foul, handball, offside, card\_yellow, card\_red, pressure, pressure\_regain, counterpress, recovery\_run, marking\_denial, decoy\_run, shape\_check, error\_leading\_to\_goal, big\_chance\_missed, injury, gk\_claim, gk\_sweep. Restarts: kickoff, throw\_in, goal\_kick, corner, free\_kick, penalty. Activities (one per player per second, never rated): stand, walk, jog, run, sprint, carry, press, track\_back, mark, make\_run, hold\_shape, talk\_ref, huddle, celebrate, down, wall, set\_piece\_wait, take\_set\_piece. Full descriptions are in Spec: Match Rules, Reactions and Audio.
- **Set pieces:** kickoff, throw-in, goal kick, corner, free kick and penalty each have a simple dot layout. The designated penalty and free-kick taker is the best on-pitch player on the Set pieces attribute (Finishing and Composure break ties); the fouled player does not take it. Penalty conversion about 75 to 80 percent, shifted by taker Set pieces and Composure against GK Shot-stopping.
- **Fouls and cards:** minor (free kick), reckless (yellow), violent or denying a clear chance (red); second yellow is red. Foul chance depends on a temperament trait (calm, normal, hot-headed), Defending and press\_intensity. Handball is rare. Award a penalty only when a defending-team player commits a direct-free-kick offence in their own penalty area; other offences in the penalty area do not result in a penalty.
- **Referee:** one extra moving entity (small solid black diamond with a thin white outline) that follows the ball at a distance. It makes the foul, card and offside decisions in code, with a roughly 3 percent error rate.
- **Red card:** the team plays with 10; the formation drops one slot and the simulator counts players on the pitch, never a fixed 11. Cut order if late: red cards, then offside.
- **Offside:** at the moment of a pass, a receiver in the opponent's half closer to the goal line than the ball and the second-last defender is offside. Result: indirect free kick, receiver -0.05.
- **Group reactions:** talk\_ref crowd after harsh calls, injury check-ups, goal celebrations (see PRODUCT). All driven by activity codes.
- **xG (chance quality):** from distance, angle, defender pressure and shot type. Bands: under 0.05 low, 0.05 to 0.25 medium, 0.25 or more big chance.

### Attributes (scale 1-99)

Final list (confirmed Oct 24): Pace, Passing, Vision, Finishing, Dribbling, Defending, Positioning, Composure, Strength, Work rate, Stamina, Set pieces, plus GK Shot-stopping for goalkeepers.

Cut: Acceleration (derived from Pace), Anticipation (folded into Positioning), GK Command.

Acceleration is derived from Pace: accel = 2.5 + 2.0 x pace / 99 m/s^2 (see Spec: Simulator Movement).

**Also added in review:** Set pieces (1-99), covering penalties and free kicks. Drives who takes them and how likely they score.

| Attribute | Drives |
| --- | --- |
| Pace | Top speed, recovery runs, winning races, time to close down |
| Passing | Pass completion |
| Vision | Pass target choice |
| Finishing | On-target and goal probability |
| Dribbling | Take-ons, keeping the ball under pressure |
| Defending | Tackle, block, interception success |
| Positioning | Marking denial, decoy runs, interceptions |
| Composure | Accuracy under pressure, passes and shots |
| Strength | Physical duels, headers |
| Work rate | How often a player presses, recovers, counterpresses |
| Stamina | Fatigue build rate |
| GK Shot-stopping (keepers only) | Save probability |

Players belong to **archetypes** (e.g. DM ball-winner, CB stopper, FB overlapper, ST poacher). An archetype sets baseline attributes; a seeded generator adds noise. Optional small "Traits" (max 0-2 per player, +5-10% on one event). Do not use EA's term "PlayStyles".

### Validation (code only, zero LLM calls)

Run 200+ seeds headless and compare means to these Premier League bands per match:

| Metric | Target |
| --- | --- |
| Passes (both teams) | 850-940 |
| Pass completion | 82-84% |
| Shots (both teams) | 22-25 |
| Shots on target | about 9 |
| Goals | 2.5-3.0 |
| Pressures per team | about 115-175 |
| Distance per outfield player | 10-12 km |
| Fouls per team | about 10-12 |

Calibrate one knob at a time: tempo, then pass intercept, then shot propensity, then xG intercept. Check that goals per team look roughly Poisson and that Azure's high press produces more pressures and distance than Redmond. After calibration, **pick a hero seed** whose totals sit near the means and that has an interesting story; this is the demo match. Several other seeds are kept for the validation report.

## 4. Rating engine

- Pure code. Consumes events and positions, emits **rating log entries**: `{event, t, player, rating: [before, after], delta, reason}`.
- Deltas, repeat decay and the soft cap are defined in Spec: Rating Model; there is no provisional period.
- Off-ball actions (pressure regain, counterpress, recovery run, marking denial, decoy run) are detected from positions plus events using explicit, documented definitions.
- Reasons are deterministic templates. The LLM may rephrase them but never invents them.
- Ratings for all 22 players are always computed.

**Added in review**

- **Soft cap:** gains scale by min(1, (10 - rating) / 3); losses by min(1, (rating - 3) / 3). Each log entry stores the raw delta, the scale factor and the final change. Ratings display to one decimal and never show 10.0 or 3.0 (range 3.1 to 9.9).
- **No provisional period.** Ratings move from the first action.
- **Shape check** every 30 to 45 s per player (position vs formation slot, work rate, tracking back), -0.05 to +0.05 or a silent "no change" entry.
- **Goalkeeper:** save = +0.1 + 0.8 x xG (cap +0.6); goal conceded = -(0.2 + 0.7 x (1 - xG)).
- **Error leading to goal:** last error before the goal gets -1.0; up to two earlier errors in the chain get -0.3 each; the simulator links the goal to its cause events.
- **Event importance** (0 to 1): base weight by event type x context (late, close score, title decider, selected player involved), nudged by rating change. 0.8 or more is ecstatic, 0.4 to 0.8 lively, 0.15 to 0.4 calm, under 0.15 filler only (used when the 15 s silence limit is reached). Code computes it; the commentator receives it as a tone tag. It also picks crowd clips and volume.

## 5. Agent pipeline

Roster (confirmed Oct 24). One job each, each reads the previous output and writes its own:

| Agent | Job | LLM? |
| --- | --- | --- |
| Interpreter | Turns raw events plus context into structured facts about a moment | light |
| Moments | Picks which moments matter and why (key moments, tactical shifts) | light |
| Commentator | Writes the selected player's commentary from facts only | yes |
| Fact Guard | Checks every claim against the event log; fixes or removes unsupported claims | validator plus LLM fix |
| Personalizer | Adapts the line to Casual or Analyst, English or Spanish | yes |

**Voice Director (added in review):** after the Personalizer, this agent takes each finished line and its tone tag and writes speaking instructions (pauses, emphasis, speed, voice style). A deterministic call to Azure AI Speech then renders audio, cached by (moment, player, mode, language). Clip duration is stored so playback can skip lower-importance lines when clips would overlap. Pipeline: Commentator, Fact Guard, Personalizer, Voice Director, text-to-speech.

**Personalizer is a separate agent (decided Oct 24).** The Commentator writes one canonical, fact-based line per moment and Fact Guard checks it once; the Personalizer then rewrites it into the four versions (Casual or Analyst, English or Spanish). This avoids running the Commentator and Fact Guard four times per moment and gives the pipeline a clear, visible handoff. Guard rule: the Personalizer may only use facts already present in the checked line and the moment's fact list, and a cheap deterministic check confirms that every number and name in each variant appears in those facts; a failed variant retries once, then falls back to the canonical line or a template. Final pipeline: Interpreter, Moments, Commentator, Fact Guard, Personalizer, Voice Director.

**Commentary cadence (decided Oct 24).** The selected player's commentary is a near-continuous stream: the gap between the end of one clip and the start of the next is at least 5 s and at most 15 s. Big moments (importance 0.8 or more: goals, red cards, penalties) may interrupt the 5 s minimum. Lines are short (about 6 to 14 words, 2 to 5 s of speech). Triggers, in priority order: a goal or card anywhere in the match; a key event involving the player (shot, key pass, tackle, foul, card); a rating change of 0.10 or more; an off-ball moment (pressure regain, counterpress, recovery run, marking denial, decoy run); and, when nothing else fires within the 15 s limit, a filler line built from code-computed facts (current activity, distance run, passes completed, rating trend, position relative to the ball, team spell). After a goal: one line immediately, a short reaction about 8 s later, then back to normal. If a line would start before the previous clip ends, the lower-importance one is dropped. Above 1x speed (2x to 10x) commentary is off and no commentary is fetched. Expect roughly 450 lines per player per match, about 1.5 times the earlier 300-moment estimate, so measure cost on a small batch; filler lines must draw on enough distinct facts to avoid repetition.

The rating engine sits beside this as a deterministic step; its output is shared state, not an LLM agent.

**Recap, overlay feed and spells (added from the challenge brief).** (1) The pipeline also produces a full-time recap per player, mode and language, pre-generated and cached like other commentary. (2) Commentary lines and rating changes are exported with `t`, `duration`, `player` and `type`, so they can drive synchronized overlays. (3) The rating engine's side computes "spells" from possession and pressure counts per 5-minute window (for example high press vs pinned back, tempo); the Moments agent tags them and the commentary may cite them. All three are code-computed facts; the LLM only words them.

**Multi-agent criteria** (judges look for these; each must be visible in the "How this was made" trace):

- **Distinct roles:** one job per agent.
- **Shared state and handoffs:** event log and rating log pass between agents as JSON.
- **Contract validation:** each agent's output is validated against its JSON schema before the next one starts.
- **Recovery from failure:** Fact Guard fixes or removes claims the event log does not support. Failed or invalid agent output retries once, then falls back to a deterministic template line. The panel shows every fix.
- **Timing:** fast deterministic steps run in sequence; slow AI steps run async and in parallel.

**Caching:** key is (match, player, mode, language, chunk), with the per-moment lines inside the chunk. Output carries `fact_check: pass|fixed|removed`.

**Must run on Microsoft Agent Framework** (not hand-rolled async), or the multi-agent category criteria are weak.

### Commentary streaming and match library (added in review)

- **Precomputed:** the simulator, event log and rating timeline of each match are computed before playback (seeded, deterministic) and stored as JSON. Seeking is instant for the pitch, ratings and rating log.
- **Commentary streams like video:** split each match into 1-minute chunks per player (90 per match). Generate the chunk at the playhead plus the next one, and cache each chunk by (match seed, player, mode, language, chunk). Chunk size and look-ahead are tunable once real call times are measured.
- **Seeking to an uncached chunk:** pitch and ratings jump at once. The commentary panel shows "Preparing commentary" and starts at the next moment when ready (target: a few seconds, to be measured). Lines that arrive more than about 10 seconds late are dropped, never read out stale.
- **Hero match and default star:** fully pre-generated (text and audio) before the demo, so the judged path never buffers.
- **Spend guard:** a daily cap on LLM chunks, set by an env var. Above the cap, uncached chunks fall back to the rating log plus short template lines (no LLM call).
- **Match library:** exactly three matches, each with a stored seed and stored simulator output, all Azure City vs Redmond United on different matchdays (there are only two clubs): the hero (3-2, matchday 38), a blowout (4-0 or 5-0, for example matchday 19) and a 1-1 draw (optionally with a red card). A 0-0 is the cheap fourth if time allows. No user-entered seeds in the UI. Extra matches get commentary only for players someone actually selects.
- **Cut order:** extra matches go before anything on the hero path.

## 6. Backend API

- FastAPI, Python 3.11+.
- The replay clock runs in the browser from the match files and never blocks on AI.
- **SSE** is not used: the match is fully precomputed, so there is nothing to push. The browser downloads the match files once and plays them back locally; commentary arrives as plain GET requests for 1-minute chunks.
- Endpoints (draft): static files at /data/matches/\<match\_id>/{meta,events,ratings,positions}.json, GET /matches (the library list), GET /commentary?match&player&mode&lang&chunk (cached 1-minute chunk, text plus audio URLs), GET /agents/trace?line=\<id> ("How this was made").
- Live LLM calls for anonymous visitors happen only for uncached commentary chunks and only under the daily spend cap (env var; it starts at 0, meaning cache and template fallback only, until the owner raises it). The hero match and default star are fully pre-generated.

## 7. Frontend

- React + Vite + Tailwind, functional components and hooks.
- SVG pitch with `viewBox="0 0 105 68"`. Dots, ball, trail and overlays are SVG layers.
- Frontend only draws simulator output; it never invents movement.
- Panels: score bar, player card (rating, sparkline, reason log), commentary (mode and language toggle), All ratings tab (vertical lineup pitch).

**Added in review**

- A star player is selected on load; there is never whole-match commentary.
- Markers: players are large team-colored numbered circles, the ball is a small white dot, the referee is a small solid black diamond with a thin white outline; goalkeepers are neon yellow (Azure) and orange (Redmond).
- Stat badges on the player card (ball per goal, boot per assist), silhouette portrait, one short animation per action type, a per-line "How this was made" link that expands the agent trace (no agent strip on screen).
- Audio: Web Audio crowd loops (murmur always on, clip and volume chosen by event importance, Azure City is the home side) plus pre-generated commentary clips. A first click unlocks audio; mute button.
- Start flow: no homepage. The first view is the Start match overlay (intro copy, Start button, Enter or Space also starts) that unlocks audio; a "Preparing match" state shows while data loads.
- Score bar centered at the top of the pitch (AZC, score, RDM, clock). A tiny card icon appears under a team's abbreviation only after that team has a card; "10 men" after a red card.
- Control bar auto-hides and is hidden by default: pause/play, 1x | 2x | 4x | 6x | 8x | 10x, a timeline with goal and card markers, and a gear that opens the View popover (Mute, Show ratings, Colorblind colors, Match info, Settings).
- Above-1x rule (2x to 10x): pitch, ratings and rating log keep running; commentary text and voice are off and no commentary chunks are fetched; crowd stays on. Only these six speeds exist: 1x, 2x, 4x, 6x, 8x, 10x.
- Right sidebar tabs: Player and All ratings. All ratings is one vertical lineup pitch (Azure top 4-3-3, Redmond bottom 4-4-2, no names) with a rating pill on each dot.
- Rating colors (default): below 5.0 red, 5.0-5.9 orange, 6.0-6.9 yellow, 7.0-7.9 light green, 8.0 and above strong green, number always visible. "Colorblind colors" switches to blue-to-orange. Lime is reserved for the selected-player ring, trail and accent.
- Dots: Azure #3B82F6, Redmond #E5484D, white outline; selected player gets a thin lime ring, one thin trail and a name tag above the dot; other dots are untagged.

## 8. Data shapes (illustrative; real schemas live in `contracts/`)

```json
{"t": 3792, "ball": [52.1, 34.0], "players": {"AZC_6": [48.2, 30.5]}}
{"id": "ev_1843", "t": 3792, "type": "pass", "player": "AZC_6", "receiver": "AZC_9", "from": [48.2, 30.5], "to": [60.0, 28.1], "outcome": "complete", "progressive": true, "difficulty": 0.4}
{"event": "ev_1843", "t": 3792, "player": "AZC_6", "rating": [7.1, 7.2], "delta": 0.1, "reason": "Progressive pass under pressure"}
{"moment": "m_212", "player": "AZC_6", "mode": "analyst", "lang": "en", "text": "...", "fact_check": "pass"}
```

Player ID format: `lowercase team abbreviation plus two-digit shirt number (e.g. azc_09); see Spec: Match Files`.

**Match files (added in review).** The simulator is a Python program run offline (`python -m sim.run --seed N`): it simulates the match, runs the rating engine on the result and writes four JSON files per match into `data/matches/<match_id>/`. FastAPI serves them as plain static files; the browser downloads all four in parallel at page load (a "Preparing match" state covers it) and after that every seek and every second of playback is local.

- `meta.json`: teams, roster (id, name, number, position, overall, gender), formations, duration, final score. A few KB.
- `events.json`: every event with a unique ID, time, type, players, from/to coordinates, outcome, xG and importance. About 1,500 to 2,000 events.
- `ratings.json`: the rating log, one entry per rating change (event ID, time, player, delta, reason). A player's rating at time t is 6.0 plus the sum of their deltas up to t, so any second can be computed in either direction.
- `positions.json`: where all 24 entities (22 players, referee, ball) are every second for the whole match (about 5,400 seconds). Compact format: one flat array of integers per entity in decimeters, `[x0, y0, x1, y1, ...]`, so index 2i and 2i+1 are x and y at second i (610, 300 means x 61.0 m, y 30.0 m). About 300 to 500 KB gzipped. The browser slides dots smoothly between seconds.

The backend reads `events.json` and `ratings.json` only when it must generate commentary for an uncached chunk (agents and Fact Guard check claims against them); it never needs positions at runtime.

**Pydantic models** (`sim/models.py`, the source of the file shapes): `Player` (attributes, gender, overall), `Team` (colors, formation; team tactics are simulator config, not part of the world file), `Event`, `RatingChange`, `Positions`, `Match` (meta plus references to the four files).

Gender field (added in review): every player has a gender field, `male` or `female`, default `male`; all generated players are `male` for now. The commentary agents pick pronouns and wording from it (he/him for `male`, she/her for `female`), and any other gender-specific logic (physical benchmarks, name pools) branches on it. No women's league or team is built for the hackathon. The field is the extension point that lets a studio adapt the system, for example to a women's competition. User-facing intro and About copy stays gender-neutral.

## 9. Storage

Plain JSON files for matches, ratings and commentary. No database. If one is added later, MongoDB documents cap at 16 MB: store one document per event, not one blob per match.

## 10. Microsoft and Azure technology (required for stage-one viability)

| Tech | Used for |
| --- | --- |
| **Microsoft Foundry** | Hosts the model deployment (small OpenAI model, e.g. gpt-4.1-nano or mini) |
| **Microsoft Agent Framework** (Python) | Orchestrates the agents and workflow |
| **Azure Container Apps** | Hosts the live app (free grant: 180k vCPU-s, 360k GiB-s, 2M requests per month) |
| **GitHub Copilot Agent Mode** | Used for real dev tasks (tests, README); mention honestly in the README |
| **Azure MCP** (optional) | Inspect or deploy resources once; mention in the README |

Azure free account: $200 credit for 30 days. Sign up early so it covers judging through Nov 10. Set a $5 budget alert.

**Azure AI Speech (text-to-speech):** free tier 0.5 million characters a month ([pricing](https://azure.microsoft.com/pricing/details/cognitive-services/speech-services)); pay-as-you-go price to confirm in the pricing calculator. Voice the default star first (about 216,000 characters for English and Spanish, both modes, at roughly 450 lines per variant; measure on a small batch), then add other players in English if budget allows.

## 11. Deployment and fallback

- One Docker container: FastAPI serves the API and the built React app.
- Azure Container Apps with min replicas 1 during judging, to avoid cold starts.
- **Saved-replay fallback:** a static build with pre-generated commentary, in case the live link or credits fail. Keep it in sync with the live version.
- Keys via environment variables. `.env` is gitignored.

## 12. Repo layout (planned)

```text
/PRODUCT.md  /ARCHITECTURE.md  /CLAUDE.md  /README.md  /TASKS.md  /TESTING.md
/contracts/        JSON schemas (events, rating changes, commentary, world)
/specs/            rating-model, match-rules, simulator-movement, simulator-possession, roster-generator, match-files, agents-backend, frontend, deployment
/docs/             decisions, research, project-summary, submission-plan, hackathon-rules (local only), gemini-ui-prompts, design-target.png, ui/ (approved screen mockups), architecture diagram, demo script
/data/             world.json, generated match JSON, commentary cache
/sim/              simulator, models (Pydantic), roster generator
/rating/           rating engine
/agents/           Agent Framework pipeline
/api/              FastAPI app
/web/              React frontend
/tests/
/Dockerfile
```

## 13. Testing approach (required for the deterministic parts; written alongside each piece)

- **Contract tests:** every JSON output validates against its schema.
- **Property tests on the simulator:** speed limit, ball on pitch, determinism, unique IDs, 11 players.
- **Evals on LLM output:** no invented facts (Fact Guard catch rate on seeded bad claims).
- **Calibration run:** benchmark table above.

## 14. Risks and fallbacks

| Risk | Fallback |
| --- | --- |
| Simulator realism takes too long | Fewer event types, simpler formations |
| Azure setup or credits fail | Smoke-test early; saved replay |
| AI latency or cost | Pre-generate and cache all hero-match commentary |
| Scope creep (3D, extras) | PRODUCT scope is final |
| Fact Guard theme is crowded | Lead the demo with the rating log and off-ball credit |

## 15. Open questions

- [x] Final attribute list: confirmed Oct 24 (12 outfield plus GK Shot-stopping)
- [x] Final agent roster: confirmed Oct 24 (Personalizer is a separate agent)
- [x] Commentary cadence: decided Oct 24 (minimum gap 5 s, maximum silence 15 s; see Commentary cadence above)
- [x] Redmond formation: 4-4-2
- [ ] Rating deltas tuning against simulator output
