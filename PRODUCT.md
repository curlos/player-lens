# PRODUCT: Player Lens

Oct 24, 2026 · @Carlos Martinez

> What we are building and why. If a feature isn't here, it's out of scope. Scope is final unless the owner says otherwise.

## One-liner

Pick any player in a live synthetic football match and follow the game through their eyes: a personal commentator and a rating that explains every change, including the off-ball work normal ratings ignore.

## Context

- Entry to the Microsoft x Premier League "Inside the Game: Developer Hackathon".
- **Personal target for submission: Tue Oct 27, 2026, 6:00 PM ET (3:00 PM PT).**
- **Official hard deadline: Tue Oct 27, 11:59 PM PT = Wed Oct 28, 2:59 AM ET.** Treat 6 PM ET as the real deadline.
- Judging runs to Nov 10. The live link must stay up through then, free and without restriction.
- Solo developer (Carlos). About 3.5 days. Every decision favors "finishable".

## Problem

Ratings on WhoScored, Sofascore and FotMob are black boxes built on on-ball events. A player who presses, tracks back and makes decoy runs gets no credit and no explanation.

## Solution

- Commentary follows the selected player, with or without the ball, not the ball. Even when a star has no touch, we still hear what he is doing: defending, pressing, tracking back.
- The rating reason log is the factual feed the commentator works from. Without it the commentator would not know what each player is doing.
- Credits off-ball work: pressure regains, counterpresses, recovery runs, marking denial, decoy runs. Also penalizes: losing the ball, failing to track back.
- Every rating change is logged with a human-readable reason.
- Commentary is personal to the selected player and tailored to the viewer: Casual or Analyst mode, English or Spanish.

## Users (real-world value)

- Fans and fantasy managers who want to follow one player.
- Broadcasters who want player-level graphics and explainable stats.
- Youth coaching that rewards work rate, not just touches.

## Intro copy (Start match overlay)

**Player Lens.** Atlas League, matchday 38. Redmond United lead Azure City by a single point, so Azure must win to take the title (owner decision Oct 26: Redmond 85 points, Azure 84; a draw or a loss leaves Redmond champions).

Pick any player and follow the match through their eyes. You get a personal commentator and a live rating that explains every change, including the off-ball work normal ratings ignore, like pressing, tracking back and decoy runs.

All players, clubs and matches are fictional. \[Start match\]

**Why it is worth building:** match ratings on the big sites are black boxes built on on-ball events, so a player who presses and tracks back gets no credit and no explanation. Player Lens shows each rating change with a reason, and the commentary follows the player, with or without the ball. Copy stays gender-neutral ("their").

## Hackathon requirements we must hit

Pipeline of five stages, all visible in the product and demo:

1. **Ingest:** synthetic match events (passes, shots, tackles, pressures, possession changes, metadata)
2. **Interpret:** stats, patterns, context
3. **Explain:** why a moment matters
4. **Render:** on-screen overlays and panels
5. **Personalize:** modes, language, player focus

Submission package:

- Public GitHub repo
- Demo video under 2 minutes (public YouTube or Vimeo URL), no third-party trademarks or copyrighted music
- Elevator pitch: what we built, which Microsoft/Azure tech, what it does, what problem it solves
- Live link, up through Nov 10
- Synthetic data only. No real clubs, players, trademarks or footage

Judging, 5 x 20%: technological implementation, agentic design, real-world impact, UX and presentation, category adherence. Stage one is pass/fail: the project must reasonably use the hero technologies (see ARCHITECTURE).

## Prize strategy

- Realistic target: **Best Multi-Agent System** (distinct agent roles, shared state and handoffs, recovery from failure, an outcome a single agent couldn't match).
- Grand Prize is a long shot.
- Second goal: a portfolio-quality repo showing full-stack, cloud deployment, agents, testing and system design in one place.
- Demo order: lead with the **player-following commentary, backed by the rating reason log**. Fact Guard is a supporting act, because "fact-checked commentary" is a crowded theme among 572+ submissions.

## The fictional world

- League: **Atlas League**
- Teams: **Azure City** (AZC, blue, 4-3-3, high press) vs **Redmond United** (RDM, red, 4-4-2, deeper block)
- All names fictional. Players are checked against a famous-player blocklist. Overlapping surnames are fine; real full names are not.
- "Azure" is used only as a color/club name: no Microsoft Azure logo or product styling in the UI or video.

**The hero match (the demo match)**

- Matchday 38 of 38: Azure City and Redmond United are the top two, and the result decides the Atlas League title. The other 18 clubs are never simulated; the title race shows only as a small static standings snippet (full league table stays a stretch feature).
- Final score 3-2 to Azure City, a close match. Other seeds (validation only) can end any way: blowouts, 0-0, 2-2. No penalty shootouts. No halftime side switch: Azure attacks left to right all match. Fouls, free kicks and yellow/red cards are in the simulator.
- Every player has a fictional overall rating (1-99) derived from attributes. Azure's star (about 90+) is the default selected player and scores 2 of the 3 goals, not all three.
- The 3-2 is not forced. We search seeds for one where Azure wins 3-2, the star scores twice and match totals sit near the Premier League benchmarks, then fix that seed as the hero match.
- Chosen hero (Oct 26, seed 9447): G. Lima (AZC #9) scores at 39', Redmond's 88' equaliser makes it 2-2, and Lima wins the title at 89'; Azure play with 10 men from 51'. The first 3-2 found (seed 2378) is kept as a backup match, not shown in the picker.
- The star is a fictional player, never a real one.
- Match library: three matches, all Azure City vs Redmond United on different matchdays (there are only two clubs): the hero (3-2, matchday 38), a blowout (4-0 or 5-0, for example matchday 19) and a 1-1 draw (optionally with a red card). Same teams and roster in every match. A 0-0 is a cheap optional fourth.

## Features (in scope)

| Feature | Behavior |
| --- | --- |
| Live synthetic match | 2D pitch, 22 dots, ball, score bar, clock, replayed from simulator output |
| Player spotlight | Click a player: lime ring, others dim, one fading trail |
| Live rating | Starts at 6.0, changes with each action, each change logs a reason |
| Off-ball credit | Pressure regains, counterpress, recovery runs, marking denial, decoy runs; negatives too |
| Personalized commentary | Feed for the selected player; Casual/Analyst; English/Spanish |
| How this was made trace | Per commentary line: which agents produced it, the handoffs and any Fact Guard fix |
| All ratings view | Ratings for all 22 players, always computed by code |

**Cut order if behind:** see CLAUDE.md and TASKS.md (extra matches, league table, Spanish, recaps, Analyst mode). Within the simulator, red cards go first, then offside.

**Never cut:** the rating reason log and the "How this was made" trace.

**Added from the challenge brief (reviewed Oct 24):**

- **Full-time recap (in scope):** one short pre-generated recap paragraph per player, mode and language, shown on the full-time card. The brief asks for automated match recaps for studio, broadcast and streaming use.
- **Overlay feed:** every commentary line and rating change carries a start time, a duration, the player and a type, so a studio could render it as a synchronized overlay on a live match feed. Documented in the README and the pitch as the integration point: swap the simulator for a feed that emits `positions` and `events` and the rest runs unchanged.
- **Explainability patterns:** the Moments agent also tags spells such as "Azure pressing high, Redmond pinned back" (control vs chaos, pressure changes, rhythm), computed in code from possession and pressure counts; the commentary may cite them.

## User flow and demo script

1. There is no homepage: the site opens straight on the match with Azure's star already selected, under a Start match overlay (short intro copy, a Start match button; Enter or Space also starts). Starting begins the replay and unlocks audio. A brief "Preparing match" state shows while data loads.
2. Within 10 seconds the judge sees the star's rating move, a reason appear in the log, and a commentary line (text and voice).
3. Click any other player: the spotlight, card, rating log and commentary all switch to him, including players who never touch the ball.
4. Toggle Casual or Analyst, English or Spanish. The commentary changes.
5. Playback controls: a play/pause button and five speeds, 1x, 2x, 4x, 10x and 30x (no speeds in between; changed Oct 26 by the owner from 1x-10x), so a full match can be watched in about 9 minutes at 10x or 3 minutes at 30x. Commentary text and voice play at 1x only. Above 1x the pitch, ratings and reason log keep running but commentary and voice are off, no commentary is fetched, and the crowd stays on. The control bar auto-hides like a video player (it appears on mouse movement or pause) and holds a timeline marking goals and cards, so a judge can jump to any moment. Below the pitch, a highlights row lists every goal, yellow card, red card and penalty (for example "88' GOAL #10 J. Ribeiro"; numbers, because the dots show numbers); clicking one jumps to a few seconds before it so the build-up plays. An optional "Activity labels" setting in the View popover shows what every player is doing (jog, hold shape, press...) under each dot. Hovering any dot shows a small tag with number, name, position, OVR and live rating. Commentary streams in 1-minute chunks (the current one plus the next) ahead of the playhead and is cached; the hero match and default star are fully pre-generated, so a jump there never buffers.
6. Click "How this was made" under any commentary line to see which agents produced it, their handoffs and any Fact Guard fix.
7. "All ratings" is a tab in the right sidebar beside the player card (not a modal, so the pitch stays visible). It shows one vertical lineup pitch (Azure on top in 4-3-3, Redmond below in 4-4-2, no names), a rating pill overlapping the bottom edge of each dot, updating live. Rating colors: below 5.0 red, 5.0-5.9 orange, 6.0-6.9 yellow, 7.0-7.9 light green, 8.0 and above strong green, number always visible; a "Colorblind colors" option in the View popover switches to blue-to-orange. Clicking a player selects him and returns to his card. A "Show ratings" toggle in the View popover (off by default) puts every player's rating above his dot; with it off, only the selected player's rating shows, and any rating pops briefly when it changes.

**2-minute video**

- 0:00-0:15: the one-line pitch and the problem.
- 0:15-0:45: star selected, a goal, rating jump with its reason, spoken commentary.
- 0:45-1:10: switch to a midfielder or defender and show off-ball credit (pressure regain, recovery run) with commentary even though he has no ball.
- 1:10-1:30: Casual to Analyst, English to Spanish.
- 1:30-1:50: "How this was made" with the agents and a Fact Guard fix.
- 1:50-2:00: the Microsoft and Azure stack and the live link.

## Pipeline stage map

| Stage | Required by the hackathon | In Player Lens |
| --- | --- | --- |
| Ingest | Synthetic match events as they happen | Simulator event stream and 1 Hz positions as JSON, unique event IDs |
| Interpret | Stats, patterns, context | Interpreter and Moments agents plus the rating engine |
| Explain | Why a moment matters | Rating reason log, event importance score, Commentator and Fact Guard |
| Render | On-screen insight beside the match | Pitch, overlays, player card, timeline, audio |
| Personalize | Modes, language, favorite player | Casual or Analyst, English or Spanish, any of 22 players, Voice Director |

Challenge extras to include where cheap: player name tags with speed and distance badges at thresholds, pass distance and a pass difficulty rating, ball and shot speed (the shot speed pop).

## Out of scope

3D graphics, substitutions, a 20-team simulated league, real data or real names, a database, user accounts, live LLM calls for anonymous visitors beyond the capped on-demand commentary chunks (see Cost rules).

## UI direction

- Dark UI, medium desaturated green pitch so dots and overlays stand out.
- Lime ring on the selected dot, no ground ring. Spotlight dims everyone else; the normal view dims no one.
- One fading trail, for the selected player only.
- Brief fading action visuals: pass line, shot line with speed pop, tackle flash, pressure pulse, rating pop.
- Pitch dots: Azure blue (#3B82F6), Redmond red (#E5484D), white outline; goalkeepers gold (Azure) and pink (Redmond), chosen to stay distinct for colorblind viewers too, no label; ball a small football; referee a small solid black diamond with a thin white outline. Lime green is reserved for the selected-player ring, trail and accent. Mockups in the Gemini UI Prompts doc are style references only; PRODUCT and the specs win.
- Layout: a simple Premier League-style score bar centered at the top of the pitch (team colors with large abbreviations and the score between them, clock at the right end; card icons appear only after a team has a card, very small under the abbreviation, with a "10 men" label after a red card; league name and matchday live in Match info, not the bar), an auto-hiding control bar along the bottom of the pitch, hidden by default (pause/play, 1x/2x/4x/10x/30x, timeline with goal and card markers) with a gear "View" popover (Mute, Show ratings, Activity labels, Colorblind colors, Match info, Settings), so nothing sits over the pitch, right sidebar with "Player" and "All ratings" tabs (selected-player card with rating and reason log, commentary panel with a per-line "How this was made" link).
- The Gemini mockup (`docs/design-target.png`) is **style and layout reference only**. It had errors that must not be copied:
  - Unique shirt numbers; exactly 11 per side, goalkeepers visible
  - Consistent spotlight dimming
  - One trail, no contradictory run arrows
  - Matching team abbreviations everywhere (AZC, RDM, not the mockup's AZU/CRC)
  - Mode toggle and text must agree
- Do not copy any other product's branding.

**Player-first rules (added in review)**

- A star player is selected on load. There is never whole-match commentary: all commentary follows the selected player.
- The layout always shows the pitch, both teams with the score, and for the selected player: rating, rating-over-time line, reason log, commentary and personal stats.
- Stat badges on the player card: a ball icon per goal, a boot per assist, plus an optional off-ball badge (for example 5+ pressure regains). Cut the off-ball badge if it clutters.
- A silhouette portrait on the player card (default avatar). No real photos.
- One short animation per action type: pass, shot, tackle or slide, interception, block, save, foul, card.
- Each commentary line has a small "How this was made" link that expands the agent trace for that line. There is no agent strip on screen.

## Rating model

Full numbers are in [Spec: Rating Model](specs/rating-model.md); match rules, activities, reactions and audio are in [Spec: Match Rules, Reactions and Audio](specs/match-rules.md). Summary:

- Every player starts at 6.0. Code computes every change; the LLM only rephrases the reason.
- Credited: goals, assists, key passes, shots on target, tackles, interceptions, blocks, clearances, aerial duels, dribbles, and off-ball work (pressure regains, counterpresses, recovery runs, marking denial, decoy runs). Penalized: dispossession, fouls, handballs, offside, cards, missed big chances, errors leading to goals.
- Goalkeepers have their own actions (saves, claims, sweeps, goals conceded), scaled by shot quality (xG).
- Every player gets a logged entry at least every 30 to 45 seconds (a small shape check, or a silent "no change").
- Soft cap: gains shrink near the top, losses near the bottom. Ratings show one decimal in a 3.1 to 9.9 range, never 10.0. No provisional period.
- Each event gets an importance score (0 to 1) that sets commentary tone and crowd reaction.

## Match rules, reactions and audio

- A referee marker (small solid black diamond with a thin white outline) follows the ball. Fouls, yellow and red cards, handballs, offside and penalty kicks are simulated. A red card means playing with 10.
- Set pieces: kickoff, throw-in, goal kick, corner, free kick, penalty. The best Set pieces player takes penalties and free kicks.
- Every player has one activity code per second (walk, run, press, track\_back, huddle, celebrate and so on). Activities never change a rating but feed commentary.
- Group reactions: teammates crowd the referee after harsh calls, check on an injured player, and join a scorer's celebration.
- Crowd sound reacts to event importance (Azure City is the home side). Commentary is spoken with Azure AI Speech, pre-generated, the default star first. Cut order for all of this is in TASKS.md.

## Cost rules

- Code computes all numbers. The LLM only writes words.
- AI runs only for the selected player.
- The hero match and the default star are fully pre-generated once (Casual/Analyst x EN/ES); every other player's commentary is generated on demand in 1-minute chunks, cached, under a daily spend cap set by an env var (it starts at 0, meaning cache and template fallback only, until the owner raises it). Visitors cost $0 unless the cap is raised.
- Small OpenAI models on the Azure free account ($200 credit, 30 days). Set a $5 budget alert. Claude in Foundry needs pay-as-you-go, so skip it.
- Keys live in env vars only, never in the repo. Anyone cloning brings their own key.

## Success criteria

- A judge can open the live link, click a player and see a rating with reasons within 10 seconds.
- The 2-minute demo shows: spotlight, rating log with an off-ball credit, commentary mode switch, "How this was made" trace with a Fact Guard fix.
- A recruiter can clone the repo, read the README, and understand the system.

## Open decisions

- [x] Redmond formation: 4-4-2 (set in review for contrast with Azure's 4-3-3; change if you prefer)
- [x] Extra attributes beyond the original 8 (see ARCHITECTURE)
- [x] Final agent roster (see ARCHITECTURE)
- [x] Commentary cadence: decided Oct 24 (at least 5 s and at most 15 s between lines; details in ARCHITECTURE)
- [x] Personalizer: separate agent (decided Oct 24)
- [x] Rating-delta tuning: Closed Oct 26 (owner): first-pass values kept as final for the hackathon; see docs/decisions.md
