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
- **Squads:** 11 starters plus about 5 bench players for realism. No substitutions in the match (`sim/models.py` allows 11-16 per squad).
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
