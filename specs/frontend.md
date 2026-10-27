# Spec: Frontend

> How the React app is built and how it maps to the approved Gemini screens. The mockups are **style and layout references only**; this spec, PRODUCT and the other specs win on any conflict. The approved images are in the Gemini UI Prompts doc and will be copied into the repo as `docs/ui/` (names below) so Claude Code can look at them.

## Stack and principles

- React + Vite + Tailwind (no named CSS classes), functional components and hooks only. SVG pitch with `viewBox="0 0 105 68"` and positions used in meters directly (see ARCHITECTURE section 2). `positions.json` stores integer decimeters, so the frontend divides by 10 to get meters before anything is drawn; nothing is ever converted to pixels in data code.
- The frontend only draws simulator output; it never invents movement, ratings or commentary.
- The match is fully local after load: one playback clock drives everything. No SSE; the only network traffic after load is commentary chunks.
- One page, no router, no homepage: the site opens on the match with a Start overlay.

## Component tree

- `App`: loads the match library and the selected match, owns the playback clock and the selection.
- `StartOverlay`: intro card with the PRODUCT intro copy (not the mockup's bullets), Start match button (Enter or Space also starts), unlocks audio. Shows "Preparing match" while files load. From `lg` up it sits over the pitch; below `lg` (phones, one-column layout) the pitch is much shorter than the card, so it covers the whole screen as a modal (rendered into `<body>`); either way the card keeps at least 16 px from the edges and scrolls rather than being cut off (owner, Oct 26). For a title decider it shows a static standings snippet: Redmond 1st on 85 points, Azure 2nd on 84 (owner decision Oct 26), so Azure must win. One constant, `STANDINGS` in `web/src/lib/config.ts`.
- `ScoreBar`: centered at the top of the pitch: AZC (blue), score, RDM (red), clock in a light box. A tiny yellow or red card icon appears under a team's abbreviation only after that team has a card; "10 men" after a red card. No league name, no matchday text in the bar.
- `Pitch` (SVG): markings, dots, ball, referee, selected-player ring, trail and name tag, action visuals, goal and penalty banners, optional rating pills.
- `PlaybackBar`: hidden by default, appears on mouse move over the pitch (not the highlights row below it; in full screen, the black bars count as pitch) or on pause, and hides 1.5 s after the mouse stops (plus a 0.3 s fade; `CONTROLS_HIDE_MS`). The mouse cursor hides with it (over the pitch, and the black bars in full screen). A control clicked with the mouse does not keep the bar open; only keyboard focus does; a play/pause button, a mute button (speaker icon, between play/pause and the clock; silences all match sound), the clock, speed buttons `1x | 2x | 4x | 10x | 30x` (the active one highlighted), timeline with goal and card markers, gear that opens `ViewPopover`, and a full-screen button last (hidden where the browser has no fullscreen, e.g. iPhone). On a narrow pitch the timeline gets its own row and the buttons split into two groups: play, mute and clock on the left; speeds, gear and full screen on the right (owner, Oct 26). Full screen shows the pitch box only, as large as the screen allows at its own 113:79 shape (about 1.43:1, not 16:9), with black bars filling the rest; Esc or the button exits.
- `HighlightsRow` (below the pitch, always visible): one chip per goal, yellow card, red card and penalty, in time order (a second yellow shares its second with the red card, so only the red chip is shown), styled in the team's color, with an icon before the label (yellow or red card shape; a football for goals; a penalty area with its spot for penalties; owner, Oct 26) and the shirt number before the name because the pitch shows numbers, not names: for example `88' GOAL #10 J. Ribeiro`, `51' RED #6 J. Pereira`, `54' PEN #10 M. Thomas`. Clicking a chip seeks to 8 seconds before the event (never below 0:00) and keeps the current play or pause state, so the build-up plays. The label uses the football minute, `floor(t / 60) + 1`: an event at 87:12 on the clock is shown as 88'.
- `ViewPopover`: Show ratings, Activity labels, Colorblind colors, All movement arrows (off by default). Movement arrows: a small, sharp, filled triangle growing out of a moving dot's white outline, pointing where the player is heading; direction only, one size. Always shown for the followed player (lime, growing out of the lime ring, above every dot) and for the 5 players nearest them within 25 m (white); the setting adds every other player, Match info (league, matchday, blurb, formations and the match picker), Settings (keyboard shortcuts; nothing else to configure yet).
- `Sidebar` with tabs `Player` and `All ratings`:
  - `PlayerCard`: silhouette avatar, name, number, position, grey "OVR 91" label, live rating pill, rating line chart (starts at 6.0), stat badges (a pill each for goals and assists: icon, count and the word, "2 goals", "0 assists", shown even at 0, with a hover tooltip explaining them; owner, Oct 26), `RatingLog`. In Analyst mode a stat line under the name reads "Expected goals (xG) 0.48 · Distance covered 5.0 km": running totals up to the playhead (sum of the player's shot xG; distance from the 1 Hz positions), with a hover tooltip explaining both (owner, Oct 26: spelled out because "xG" and a bare "Distance" were confusing).
  - `CommentaryPanel`: Casual/Analyst toggle, EN/ES toggle, the lines, "Preparing commentary" state, and a per-line "How this was made" link that expands `AgentTrace`.
  - `AllRatings`: one vertical lineup pitch (Azure on top in 4-3-3, Redmond below in 4-4-2, no names), each side labelled with a pill in its team colour, name and abbreviation as on the score bar ("Azure City (AZC) 4-3-3", owner, Oct 26), a rating pill overlapping the bottom edge of each dot, updating live.
- `FullTimeCard`: final score, "Atlas League champions" for a title decider (the champion follows from `STANDINGS` plus the result: only an Azure win overtakes Redmond), the selected player's match rating, top three rating moments, recap paragraph, `Replay match` and `Pick another player`.
- `MatchPicker` (in both the Start overlay and Match info): the three matches of the library with matchday and result. The hero match is preselected; the Start overlay shows the others as a small "Other matches" line under the Start button, and Match info lists the same three so a viewer can switch later.

## Data loading

1. `GET /matches` returns the library list. In dev and `vite preview`, `web/scripts/match-data-plugin.ts` answers it and serves `/data/...` straight from the repo-root `data/` folder (nothing is copied into `web/`); FastAPI takes over both in Phase 3.
2. For the chosen match, fetch `meta.json`, `events.json`, `ratings.json` and `positions.json` in parallel as static files (see ARCHITECTURE section 8). Show "Preparing match" until all four are parsed.
3. Parse positions once into typed arrays (for example one `Int16Array` per entity, decimeters) so per-frame reads are cheap. Convert to meters (value / 10) when reading a sample for rendering, so every drawn x is 0 to 105 and y is 0 to 68, matching the `viewBox`.
4. Build lookups once: events sorted by time; per-player cumulative rating arrays indexed by second (rating at time t = 6.0 plus the sum of deltas up to t); score and card timelines; timeline marker list.
5. Commentary: `GET /commentary?match&player&mode&lang&chunk` for the 1-minute chunk at the playhead plus the next one; cache chunks in memory keyed by (match, player, mode, lang, chunk). Everything goes through one function, `getCommentaryChunk(match, player, mode, lang, chunk)` in `web/src/lib/commentary.ts`, plus `getTrace(lineId)`. Phase 2 implements them with code-built template lines (`fact_check: "template"`, `audio_url: null`, a single `Template` trace step); Phase 3 swaps their bodies for the HTTP calls.
6. TypeScript types for every file are generated from `contracts/*.schema.json` (`npm run gen:types`, output in `web/src/types/generated/`); never hand-write them.

## Playback clock

- A single state `{ t, playing, rate }` with `rate` 1, 2, 4, 10 or 30 (no other values; owner decision Oct 26, matching the dev viewer `scripts/viewer.html`; a full match takes 3 minutes at 30x). A `requestAnimationFrame` loop advances `t` by elapsed real time x rate while playing.
- Seeking sets `t` directly (instant: positions, events and ratings are local). Keyboard: Space pauses, left and right arrows seek 5 seconds, Enter or Space also starts from the overlay.
- The pitch reads `t`, finds seconds `floor(t)` and `ceil(t)` and linearly interpolates each entity's position (in meters, after the decimeter conversion) so dots glide. Everything else (score, cards, ratings, log, markers) is derived from `t` by lookup.
- The clock never waits on commentary, audio or any network call.

## Selection and visual rules

- A star is selected on load (AZC #9, `azc_09`; the name comes from `data/world.json`, currently G. Lima). Clicking any dot selects that player: the card, rating log, commentary and the pitch spotlight switch to them.
- Selected player: thin lime ring (outline only), one thin fading trail, and a name tag above the dot (translucent dark pill, for example "G. Lima #9" with the number in lime, a small notch toward the dot, drawn under all dots). No tags on other players.
- Sent-off player: the dot walks to the bottom touchline (activity `sent_off`), then fades out over about 2 s once it stops; the red card stays visible on the score bar ("10 men"). If that player is selected, the card and log stay available.
- Keyboard on the pitch: the pitch is one tab stop (a listbox of players, `aria-activedescendant`). Focus starts on the followed player; arrow keys move to the nearest player in that direction (dashed white ring plus the hover tag; screen readers read the player); Enter or Space follows that player; Home goes back to the followed player; Tab leaves the pitch for the playback bar. On the pitch the arrows move between players instead of seeking.
- Hover tag: hovering any player dot (pointer devices only) shows a small tag above it for as long as the pointer stays: shirt number, name, slot (the formation label such as ST, LW, RB, CM, from `meta.json`), OVR and the live match rating, for example `#9 G. Lima · ST · OVR 91 · 7.4`, with the rating as a colored pill (rating colors below). Same dark pill style as the selected player's name tag, drawn above all dots so it is never hidden. It is read-only: clicking still selects. No tag for the referee or the ball. On touch screens a tap selects the player instead, so the player card carries this information. On both the name tag and the hover tag the rating pill sits a fixed 0.7 m after the text, whose width is measured in the browser (not estimated from the letter count).
- Spotlight mode dims every other dot **and the referee** to about 35%; normal view dims nobody; never dim only some dots. Spotlight turns on for about 7 match seconds after an event of importance 0.8 or more that involves the selected player (goal, penalty, card) and for about 2.5 s after a click (owner, Oct 26: the dim is instant, then eases out: after a click it holds 1.5 s and fades back over 1 s; after a big moment it fades over the last 1.5 match seconds) selects a player; otherwise the view is normal (Phase 2 reading of PRODUCT "click a player: others dim" plus this spec's "normal view dims nobody").
- Dots: about 26 px at the reference size, Azure blue `#3B82F6`, Redmond red `#E5484D`, shirt number in bold white, thin white outline and a soft dark shadow. Goalkeepers are gold `#FACC15` (Azure) and pink `#F472B6` (Redmond) with a dark number and no label (owner decision Oct 26: chosen to stay distinct from both kits, each other, the pitch, the ball and the referee for colorblind viewers too; the frontend uses `KEEPER_COLORS` in `web/src/lib/config.ts` instead of `meta.json` `keeper_color`). Numbers 1 to 11 are unique per team. Ball: a small football (white with black patches, about 15 px, still smaller than a dot) with a thin dark outline and soft shadow (owner, Oct 26). It is drawn at its true position (the interpolated 1 Hz track), also when carried; the one exception is a shot (owner, Oct 26): for the ~0.4 s after a kick it flies the shot event's `from` to `to` line at `speed_kmh`, holds at the target, then eases into the next track sample, because the 1 Hz track would glide it over a whole second. The GOAL banner, the goal-net flash, the score bar, the goal's highlight chip, the rating pops of that second, the GOAL commentary line and the crowd wait until the ball has landed (`goalRevealT` / `shownAt`, from `revealAt` built once per match); everything else (shot line, xG chip, rating log) stays on the kick (it then covers the shirt number); drawing it on the carrier's rim was tried and dropped because it swung around the dot on every touch. Referee: small solid black diamond with a thin white outline.
- Pitch: dark desaturated forest green `#2E5A30` with very subtle mowing stripes running across the length, white lines at about 60% opacity. Lime green is reserved for the selected-player ring, trail and accents.
- Rating colors (pills, All ratings): below 5.0 red, 5.0 to 5.9 orange, 6.0 to 6.9 yellow, 7.0 to 7.9 light green, 8.0 and above strong green; the number is always visible. `Colorblind colors` (View popover, off by default) switches to blue-to-orange. Rating log deltas (also the full-time card's top moments and the rating pops on the pitch): green with `+`, red with `-`; with `Colorblind colors` on they are blue and orange too, and the sign always stays (owner, Oct 26). The OVR label is neutral grey, never colored.
- `Activity labels` (toggle in the View popover below Show ratings, off by default, remembered per viewer; owner, Oct 26: moved out of the control bar): shows each player's current activity from `positions.json` (`act`, looked up in `meta.activities`) as small text under every dot, with underscores as spaces ("hold shape", "track back", "jog"). Off: no activity text at all, not even for the followed player (owner, Oct 26: the commentary covers what they are doing); only special labels such as "Celebrating" remain. The referee has no label. Same look as the dev viewer.
- `Show ratings` (View popover, off by default) puts every player's rating pill above their dot; with it off only the selected player's rating shows (as a pill inside the name tag), and a rating pop appears briefly when a rating changes (every change for the selected player; for others only changes of 0.05 or more, `POP_MIN_DELTA_OTHERS`, so routine duel credit doesn't clutter the action).
- GOAL banner (owner, Oct 26): solid in the scoring team's colour (`#3B82F6` or `#E5484D`), fading to transparent at both ends, with bold white text ("GOAL - #9 G. Lima 39'", with the shirt number because the pitch shows numbers, not names) and a soft dark text shadow. The PENALTY banner stays orange on dark, so the two never look alike.
- Brief fading action visuals: pass line, shot line with speed pop (for example "112 km/h"), tackle flash, pressure pulse, rating pop; banners for goals and penalties; a small "Celebrating" label under a scorer.

## Commentary, trace and audio

- Commentary lines carry `t`, `duration`, `player`, `type`, text and an audio URL. A line shows when `t` reaches its start; a new line replaces the old after its duration.
- Seeking to an uncached chunk: pitch and ratings jump at once; the panel shows "Preparing commentary" and resumes at the next line when the chunk arrives. Lines that arrive more than about 10 seconds late are dropped.
- **Above-1x rule (2x to 30x):** pitch, ratings and rating log keep running; commentary text and voice are off with the message "Commentary pauses at {rate}x speed" (`{rate}` is the current rate, so 2x shows "Commentary pauses at 2x speed"; 3x is not a valid rate); the crowd stays on. No commentary requests are made while the rate is above 1; when the rate returns to 1x, fetch the chunk at the playhead plus the next one and show "Preparing commentary" until it arrives. Changing speed stops any clip that is playing.
- "How this was made" expands a compact vertical trace in the panel: Interpreter, Moments, Commentator, Fact Guard (amber badge and a before/after diff when it fixed something), Personalizer (mode and language), Voice (clip length). Data comes from `GET /agents/trace?line=<id>`. There is no agent strip anywhere else.
- Audio: the crowd is built (Phase 2, owner Oct 26; rules in Spec: Match Rules, "Crowd sound"): a looped murmur that swells near the goals, reaction clips for goals, chances, penalties and cards (Azure City is the home crowd), and a real referee whistle, all driven by `crowdCues` in `web/src/lib/crowd.ts` from the clock. Commentary clips follow in Phase 3, with the crowd ducked under the voice. The Start click unlocks audio; the only Mute control is the speaker button in `PlaybackBar`.
- Language and mode toggles switch the line shown; UI labels stay English, commentary and rating-log reasons are localized.

## Rating log reason text

`ratings.json` stores a `reason_code` and `values`, never text (specs/match-files.md). The frontend owns one EN and one ES template per code, filled from `values`; player ids in `values` are shown as `#number name` from `meta.json`, `xg` with two decimals, distances in meters. Entries with `delta` 0 (`shape_no_change`) are silent: never shown in the log. Codes marked off-ball have `off_ball: true` and can carry a small "off-ball" tag.

| reason_code | values | Off-ball | Meaning (draft EN) |
| --- | --- | --- | --- |
| goal | xg | | Scored (xG {xg}) |
| assist | scorer | | Assisted {scorer} |
| key_pass | receiver | | Key pass to {receiver} |
| shot_on_target | xg | | Shot on target (xG {xg}) |
| big_chance_missed | xg | | Missed a big chance (xG {xg}) |
| tackle | opponent | | Won the ball from {opponent} |
| dispossessed | opponent | | Dispossessed by {opponent} |
| interception | passer | | Intercepted {passer}'s pass |
| block | shooter | | Blocked {shooter}'s shot |
| clearance | | | Cleared the danger |
| aerial_duel_won | opponent | | Won a header against {opponent} |
| dribble | opponent | | Beat {opponent} |
| beaten_by_dribble | opponent | | Beaten by {opponent} |
| foul_won | opponent | | Fouled by {opponent} |
| foul_committed | opponent | | Fouled {opponent} |
| handball | | | Handball |
| offside | | | Caught offside |
| card_yellow | | | Yellow card |
| card_red | | | Sent off |
| error_leading_to_goal | | | Error leading to a goal |
| error_leading_to_goal_earlier | | | Mistake in the move that led to a goal |
| gk_save | xg, shooter | | Saved from {shooter} (xG {xg}) |
| gk_goal_conceded | xg, scorer | | Beaten by {scorer} (xG {xg}) |
| gk_claim | opponent | | Claimed the cross |
| gk_sweep | opponent | | Swept up behind the defence |
| counterpress | opponent | yes | Pressed {opponent} straight after losing the ball |
| pressure_regain | opponent | yes | Pressed {opponent} and the team won the ball back |
| recovery_run | distance_m | yes | Sprinted {distance_m} m back to defend |
| marking_denial | opponent, seconds | yes | Marked {opponent} out of the game |
| decoy_run | teammate, opponent | yes | Run dragged {opponent} away, freeing {teammate} |
| shape_kept | deviation_m | yes | Held position in the team shape |
| shape_out_of_position | deviation_m | yes | Out of position ({deviation_m} m from shape) |
| shape_walking | deviation_m | yes | Walking while out of position |
| shape_no_change | deviation_m (optional) | yes | Silent (never shown) |

The English text is a draft for the frontend build; Spanish is written alongside it. Optional keys may be missing (for example `key_pass` without `receiver`), so templates must not fail on a missing value.

## Full time

At the end of the match the pitch dims and `FullTimeCard` appears. `Replay match` restarts at 0:00; `Pick another player` returns to the match with player selection (click any dot or choose from the All ratings tab).

## Screen map (approved Gemini images, style reference only)

| # | State | Repo image | What it shows |
| --- | --- | --- | --- |
| base | Base layout | `docs/ui/00-base-layout.png` | Overall layout, colors, score bar, sidebar |
| 1 | Start overlay | `docs/ui/01-start-overlay.png` | Intro card, Start match, match context, empty player card, disabled playback bar |
| 2 | Live play | `docs/ui/02-live-play.png` | Normal view, selected player, rating log, commentary, hidden playback bar |
| 3 | Goal | `docs/ui/03-goal.png` | Shot line with speed pop, GOAL banner, rating pop, excited commentary, spotlight on |
| 4 | Celebration | `docs/ui/04-celebration.png` | Scorer celebrating with teammates converging, "Celebrating" label |
| 5 | All ratings | `docs/ui/05-all-ratings.png` | Vertical lineup pitch with rating pills |
| 6 | Show ratings + trace | `docs/ui/06-show-ratings-and-trace.png` | Pills on all dots, View popover, expanded "How this was made" |
| 7 | Yellow card | `docs/ui/07-yellow-card.png` | Foul, card icon under RDM, caption |
| 8 | Red card and 2x | `docs/ui/08-red-card-2x.png` | 10 men label, playback bar visible with 2x, commentary paused |
| 9 | Penalty | `docs/ui/09-penalty.png` | PENALTY banner, xG chip, spotlight (real rule: only the taker and the keeper are inside the box) |
| 10 | Full time | `docs/ui/10-full-time.png` | Full-time card, top rating moments, Replay, Pick another player |
| 11 | Analyst + Spanish | `docs/ui/11-analyst-spanish.png` | Spanish text and log reasons, xG and distance stat line |

## Known mockup errors (do not copy)

- Garbled or misspelled small text, stray axis labels, duplicate shirt numbers, Redmond dots in a dark maroon instead of `#E5484D`, missing referee, a wrong subtitle under the player name, extra gear icons on the timeline, and players crowding the box in the penalty screen.
- The mockups show the playback bar only where a screen needs it; in the real app it is hidden by default.

## Performance and robustness

- 24 SVG entities and a handful of overlays: plain SVG with per-frame attribute updates is enough; avoid re-rendering React trees per frame (update refs or a small canvas-free SVG layer).
- Everything derived from `t` is O(1) or O(log n) per frame (lookups into prebuilt arrays).
- Type sizes (owner, Oct 26): 14 px for anything meant to be read (rating log, highlights, playback bar, cards, popover, links), 12 px minimum for small labels (column headers, OVR chip, off-ball tag, chart tooltip and axis); only the "10 men" badge is smaller. Commentary is 15 px. Sidebar 360 px (400 px on wide screens).
- Scrollbars (owner, Oct 26): thin and grey everywhere (thumb `#52525b` on track `#27272a`, set once with `scrollbar-color` in `web/src/index.css`) instead of the bright browser default on the dark UI.
- Browser storage is not needed for correctness; any use (for example the chosen language) is wrapped in try/catch.

## Open questions

- Whether to add a small minimum-distance nudge between dots if overlaps look bad (see Spec: Simulator Movement).
- Decided: the match picker lives in both the Start overlay and Match info (see the component tree).
