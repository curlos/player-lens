# Decisions log: why we chose what we chose

> Context that was discussed in planning but isn't in PRODUCT or ARCHITECTURE. If a decision here conflicts with those, flag it; don't silently pick one. Open (unanswered) decisions are in TASKS.

## World and naming

- **League:** Atlas League (owner's choice; a generic word).
- **Teams:** Azure City (AZC, blue) and Redmond United (RDM, red).
  - "Azure" is also an ordinary color and word, and the judges are Microsoft people who will get the wink.
  - Rule 11.8 reserves Microsoft's and the Premier League's IP "to the extent provided for in these Official Rules", and the rules say nothing about club names, so this is a gray area. Risk is low; keep it safe by using "Azure" only as a color/club name, with no Azure logo or product styling in the UI or video.
  - "Redmond" is Microsoft's HQ city (a place name, not a trademark). Don't name clubs after products (Copilot, Foundry, Fabric).
  - The mockup's AZU/CRC abbreviations are replaced everywhere by AZC/RDM.
- **Names:** all fictional, mixed nationalities, as a real league would have. A famous-player blocklist check is part of the roster generator (not built yet). Overlapping surnames are fine; real full names are not. An AI can't guarantee a name isn't some obscure real pro, so the owner spot-checks the final list.
- **Squads:** 11 starters, no bench, no substitutions (stale earlier note said about 5 bench players; the roster spec and `sim/models.py` have exactly 11 per team).
- **Redmond's formation:** 4-4-2, for tactical contrast with Azure's 4-3-3 (decided).
- Gender field: every player has gender (default `male`); all generated players are male for now. User-facing copy stays gender-neutral.

## Scope

- **2D dots, not 3D:** cheaper and more reliable in 3.5 days; the value is the data and explanations.
- **Two clubs, not a 20-team league.** A league table with about 20 fictional club names and a scoreline-only season sim (about 30 minutes) is a stretch feature and the first thing cut after the extra matches.
- **Match library: three matches**, all Azure City vs Redmond United on different matchdays: the hero (3-2, matchday 38), a blowout (4-0 or 5-0) and a 1-1 draw. A 7-0 was rejected as too rare to produce realistically. A 0-0 is an optional fourth. Validation runs are code only (no LLM calls); 10-20 seeds is plenty for the report, and 200+ for calibration.
- **No halftime:** Azure attacks left to right the whole match; sides never switch.
- **Personalizer** is added as a stage (matches the "personalize" pipeline stage). It's the same LLM call with a mode and language instruction, not a translation library, so the extra cost is negligible. Decided Oct 24: it is a separate agent. The Commentator writes one canonical line per moment, Fact Guard checks it once, and the Personalizer makes the four variants, so the Commentator and Fact Guard do not run four times; a code check confirms every number and name in a variant appears in the checked facts.
- **Deploy on Azure Container Apps**, not Vercel (even though the owner usually deploys on Vercel). One Docker container serves the API and the built React app.

## Data and simulation

- **Python for the simulator:** numpy, Pydantic and the Agent Framework Python SDK keep the backend one language. React stays on the frontend.
- **Run offline, serve files.** Simulating is fast; the reason to run it offline is that every visitor sees the same fixed match and the commentary is written against exactly those events. The browser downloads four static files per match (`meta`, `events`, `ratings`, `positions`) and plays them back locally, so there is no SSE.
- **Code makes the numbers, LLM makes the words.** A Monte Carlo simulator is just weighted dice per event, repeated; the seed makes it repeatable.
- **Two-step events (decide, then execute)** borrowed from Football Manager. EA's engine internals are unpublished, so we borrow EA's attribute structure, not its engine.
- **Attributes:** final list confirmed Oct 24: Pace, Passing, Vision, Finishing, Dribbling, Defending, Positioning, Composure, Strength, Work rate, Stamina, Set pieces, plus GK Shot-stopping for keepers. Acceleration is derived from Pace; Anticipation is folded into Positioning. Fuller set in the attributes research doc.
- **No teleporting** is guaranteed by construction: positions change only in `move_player()`, speed-capped. Property tests (not written yet) will check it.
- **Pitch:** 105 x 68 m, meters, origin top-left; the SVG uses `viewBox="0 0 105 68"` so data and screen can't disagree. Positions are saved every second, compactly (flat integer arrays in decimeters); the frontend interpolates between them.
- **Pydantic design:** `extra="forbid"` so typos fail loudly; `team.short` duplicates `team.id` but is validated to match; goalkeeper-only `gk_shot_stopping` lives on Player; attributes are nested under `attributes`.

## Phase 1 build (Oct 25)

Choices made while building the match data, where the docs left room or disagreed. All knobs live in `sim/config.py` and `rating/config.py`.

- **Star name (owner decision).** The star is AZC #9 (`azc_09`), the highest-OVR Azure player, named by the generator like everyone else (Gabriel "G. Lima", Brazil). "R. Valdemar" in the frontend spec, match-files example and mockups was a placeholder; those specs now point at `data/world.json`.
- **Event ids** follow Spec: Match Files (`e_0001`), not ARCHITECTURE's illustrative `ev_1843` (ARCHITECTURE updated).
- **Event count** is about 4,500 to 5,500, not 1,500 to 2,000: every rating entry must point to an event, so the 30 to 45 s shape checks are events (roughly half the file). A shape check is added only when a player has had no other rating entry for 30 to 45 s.
- **Bench:** the "11 starters plus about 5 bench players" line above is stale; the roster spec and models have 11 per team and no bench.
- **Sent-off players** walk (via `move_player()`) to the bottom touchline (y = 68, x = 45 for Azure, 60 for Redmond, set in `sim/config.py`), away from the score bar at the top center, and stay there with a new activity code `sent_off`, so every position stays on the pitch. The frontend fades the dot out once they arrive (owner decision Oct 26). If a back-four player is sent off, the DM/CM #6 takes their slot.
- **Shot speed** is capped at 108 km/h, because the ball cap is 30 m/s (the spec example shows 112).
- **Blocklist** syntax: one word or `surname: X` blocks a surname, two or more words block a full name. Famous surnames from the pools (Van Dijk, De Jong, De Vries, Gomes) are blocked so no player reads as a famous one.
- **Stopping rule** uses the exact per-tick braking sum (the spec allows "a short loop or closed form"); the `u (u + a) / (2a)` approximation let players overshoot touchlines. A per-axis wall cap keeps the acceleration limit true at the lines too.
- **Calibration changes beyond the research formulas** (see `docs/validation-report.md`): pass completion gets a receiver-marking term and a harder "pass into the box" term; crosses complete less often; a goal-side defender stops a carrier running straight at goal; near their own goal the two nearest defenders always press. Passing and duel skill sensitivity were softened (`PASS_Z` 0.18, `DUEL_SKILL` 0.22) and Redmond's tactics set to press 0.5, line 0.45 (still a deeper block than Azure's 0.8 and 0.7) so a title decider between first and second is not one-sided: Azure win about 58%, draw 22%, Redmond 19% over 200 seeds.
- **Pressure** counts a presser closing in (moving at 3+ m/s) within 1.1 m of the carrier, once per presser and carrier per 30 s; this lands pressures per team inside 115 to 175.
- **Rating tuning (first pass):** repeat decay `max(0.25, 0.85^n)`; shape-check credit +0.02 only for staying within 3 m of the shape target while working; a pressure regain needs the presser within 10 m of the ball when it is won. Mean final rating about 7.0 (SD 0.8).
- **Accepted as is (owner, Oct 26):** ratings run slightly high (mean about 7.0 vs about 6.7 on real sites), and the simulator produces too many duels (a striker can attempt about 20 dribbles a match vs 2 to 4 in real football; repeat decay keeps the rating effect small). Fixing duels would change every match and the library seeds, so neither is tuned further for the hackathon.
- **Off-ball thresholds** (recovery run 12 m in 8 s ending goal-side, marking denial 2.5 m for half of a 5-minute window with no pass received, decoy run drags a defender 6 m while a teammate gets 4 m of space) are guesses, listed in `rating/config.py`.
- **Penalty event** is logged when the penalty is awarded (outcome `awarded`); the kick itself is a `shot`. Other restarts are logged when taken.
- **Library seeds** come from `scripts/find_seeds.py` (criteria in its docstring) and are stored in `sim/library.py`.
- **Hero match (owner pick, Oct 26):** seed 9447. 2-2 after Redmond's 88' equaliser, then Lima's 89' title winner; Azure play with 10 men from 51' (J. Pereira, second yellow). The exact "2-2 from mid-match until a winner after 85'" pattern was not found in 16,000 seeds; the two closest both had a late equaliser, and 9447 was picked because the climax belongs to the default player. The first hero (seed 2378: Lima twice, 83' penalty winner by M. Thomas) is kept as `md38_title_decider_backup`, built and tested but not listed in the picker. Any change to the world or the simulator changes every match, so re-run the search after one.

- **Spells built early (Oct 26):** `rating/spells.py` labels each 5-minute window (`control`, `high_press`, `end_to_end`, `even`) from `events.json` only, so the agent pipeline can call it at runtime without positions. Not written into the match files (the four-file contract stays as is). Thresholds are guesses tuned to the library matches.

## Playback controls (owner, Oct 26)

- **Speeds are 1x, 2x, 4x, 10x, 30x** (was 1x-10x in six steps), copied from the dev viewer so a full match can be skimmed in 3 minutes. Commentary still plays at 1x only.
- **Highlights row** below the pitch: goals, cards and penalties as chips; a click seeks to 8 s before the event so the build-up plays. Labels use the football minute (87:12 shows as 88').
- **Activity labels** checkbox in the control bar, off by default: every dot shows what that player is doing (jog, hold shape, press...).
- **Shirt numbers in highlight chips** (`88' GOAL #10 J. Ribeiro`), because the pitch shows numbers, not names.
- **Hover tag** on any player dot: number, name, position, OVR and live match rating. Frontend only; the data is already in `meta.json` and `ratings.json`.

## Presentation

- **Lead the demo with the rating reason log and off-ball credit**, not Fact Guard ("fact-checked commentary" is a crowded theme among 572 submissions).
- **The mockups are style/layout references only.** The Gemini UI Prompts doc holds the approved screens. Where they disagree with PRODUCT or the specs, the docs win (for example, in a penalty only the taker and the keeper are in the box).
- **"How this was made"** replaces the agent strip: a per-line link that expands the agent trace.
- **Rating colors:** red-to-green by default with a "Colorblind colors" option (blue-to-orange) in the View popover.

## Deadline

- Submission window closes Tue Oct 27, 2026, 11:59 PM PT = Wed Oct 28, 2:59 AM ET (both zones on daylight time until Nov 1).
- Owner's personal target: submit by Tue 6:00 PM ET (3:00 PM PT), leaving about 9 hours of cushion.

## Not yet reviewed

- The challenge brief text was reviewed Oct 24 and folded into PRODUCT (recap, overlay feed, explainability patterns). Not seen: any event-format details on the website's Challenge page itself.
- Commentary-pacing research is still not reviewed, but the cadence is decided (Oct 24): a near-continuous stream with at least 5 s and at most 15 s between lines, because the owner wants the player to feel followed at all times.
