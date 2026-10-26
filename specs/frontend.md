# Spec: Frontend

> How the React app is built and how it maps to the approved Gemini screens. The mockups are **style and layout references only**; this spec, PRODUCT and the other specs win on any conflict. The approved images are in the Gemini UI Prompts doc and will be copied into the repo as `docs/ui/` (names below) so Claude Code can look at them.

## Stack and principles

- React + Vite + Tailwind (no named CSS classes), functional components and hooks only. SVG pitch with `viewBox="0 0 105 68"` and positions used in meters directly (see ARCHITECTURE section 2). `positions.json` stores integer decimeters, so the frontend divides by 10 to get meters before anything is drawn; nothing is ever converted to pixels in data code.
- The frontend only draws simulator output; it never invents movement, ratings or commentary.
- The match is fully local after load: one playback clock drives everything. No SSE; the only network traffic after load is commentary chunks.
- One page, no router, no homepage: the site opens on the match with a Start overlay.

## Component tree

- `App`: loads the match library and the selected match, owns the playback clock and the selection.
- `StartOverlay`: intro card, Start match button (Enter or Space also starts), unlocks audio. Shows "Preparing match" while files load.
- `ScoreBar`: centered at the top of the pitch: AZC (blue), score, RDM (red), clock in a light box. A tiny yellow or red card icon appears under a team's abbreviation only after that team has a card; "10 men" after a red card. No league name, no matchday text in the bar.
- `Pitch` (SVG): markings, dots, ball, referee, selected-player ring, trail and name tag, action visuals, goal and penalty banners, optional rating pills.
- `PlaybackBar`: hidden by default, appears on mouse move or pause; a play/pause button, speed buttons `1x | 2x | 4x | 10x | 30x` (the active one highlighted), timeline with goal and card markers, an `Activity labels` checkbox, gear that opens `ViewPopover`.
- `HighlightsRow` (below the pitch, always visible): one chip per goal, yellow card, red card and penalty, in time order, styled in the team's color, with the shirt number before the name because the pitch shows numbers, not names: for example `88' GOAL #10 J. Ribeiro`, `51' RED #6 J. Pereira`, `54' PEN #10 M. Thomas`. Clicking a chip seeks to 8 seconds before the event (never below 0:00) and keeps the current play or pause state, so the build-up plays. The label uses the football minute, `floor(t / 60) + 1`: an event at 87:12 on the clock is shown as 88'.
- `ViewPopover`: Mute, Show ratings, Colorblind colors, Match info, Settings.
- `Sidebar` with tabs `Player` and `All ratings`:
  - `PlayerCard`: silhouette avatar, name, number, position, grey "OVR 91" label, live rating pill, rating line chart (starts at 6.0), stat badges (ball per goal, boot per assist, shown even at 0), `RatingLog`.
  - `CommentaryPanel`: Casual/Analyst toggle, EN/ES toggle, speaker icon, the lines, "Preparing commentary" state, and a per-line "How this was made" link that expands `AgentTrace`.
  - `AllRatings`: one vertical lineup pitch (Azure on top in 4-3-3, Redmond below in 4-4-2, no names), a rating pill overlapping the bottom edge of each dot, updating live.
- `FullTimeCard`: final score, "Atlas League champions" when applicable, the selected player's match rating, top three rating moments, recap paragraph, `Replay match` and `Pick another player`.
- `MatchPicker` (in both the Start overlay and Match info): the three matches of the library with matchday and result. The hero match is preselected; the Start overlay shows the others as a small "Other matches" line under the Start button, and Match info lists the same three so a viewer can switch later.

## Data loading

1. `GET /matches` returns the library list.
2. For the chosen match, fetch `meta.json`, `events.json`, `ratings.json` and `positions.json` in parallel as static files (see ARCHITECTURE section 8). Show "Preparing match" until all four are parsed.
3. Parse positions once into typed arrays (for example one `Int16Array` per entity, decimeters) so per-frame reads are cheap. Convert to meters (value / 10) when reading a sample for rendering, so every drawn x is 0 to 105 and y is 0 to 68, matching the `viewBox`.
4. Build lookups once: events sorted by time; per-player cumulative rating arrays indexed by second (rating at time t = 6.0 plus the sum of deltas up to t); score and card timelines; timeline marker list.
5. Commentary: `GET /commentary?match&player&mode&lang&chunk` for the 1-minute chunk at the playhead plus the next one; cache chunks in memory keyed by (match, player, mode, lang, chunk).

## Playback clock

- A single state `{ t, playing, rate }` with `rate` 1, 2, 4, 10 or 30 (no other values; owner decision Oct 26, matching the dev viewer `scripts/viewer.html`; a full match takes 3 minutes at 30x). A `requestAnimationFrame` loop advances `t` by elapsed real time x rate while playing.
- Seeking sets `t` directly (instant: positions, events and ratings are local). Keyboard: Space pauses, left and right arrows seek 5 seconds, Enter or Space also starts from the overlay.
- The pitch reads `t`, finds seconds `floor(t)` and `ceil(t)` and linearly interpolates each entity's position (in meters, after the decimeter conversion) so dots glide. Everything else (score, cards, ratings, log, markers) is derived from `t` by lookup.
- The clock never waits on commentary, audio or any network call.

## Selection and visual rules

- A star is selected on load (AZC #9, `azc_09`; the name comes from `data/world.json`, currently G. Lima). Clicking any dot selects that player: the card, rating log, commentary and the pitch spotlight switch to them.
- Selected player: thin lime ring (outline only), one thin fading trail, and a name tag above the dot (translucent dark pill, for example "G. Lima #9" with the number in lime, a small notch toward the dot, drawn under all dots). No tags on other players.
- Sent-off player: the dot walks to the bottom touchline (activity `sent_off`), then fades out over about 2 s once it stops; the red card stays visible on the score bar ("10 men"). If that player is selected, the card and log stay available.
- Hover tag: hovering any player dot (pointer devices only) shows a small tag above it for as long as the pointer stays: shirt number, name, slot (the formation label such as ST, LW, RB, CM, from `meta.json`), OVR and the live match rating, for example `#9 G. Lima · ST · OVR 91 · 7.4`, with the rating as a colored pill (rating colors below). Same dark pill style as the selected player's name tag, drawn above all dots so it is never hidden. It is read-only: clicking still selects. No tag for the referee or the ball. On touch screens a tap selects the player instead, so the player card carries this information.
- Spotlight mode dims every other dot **and the referee** to about 35%; normal view dims nobody; never dim only some dots.
- Dots: about 26 px at the reference size, Azure blue `#3B82F6`, Redmond red `#E5484D`, shirt number in bold white, thin white outline and a soft dark shadow. Goalkeepers are neon yellow `#E6F23A` (Azure) and orange `#FF9F1C` (Redmond) with a dark number and no label. Numbers 1 to 11 are unique per team. Ball: small white dot (about 12 px) with a thin dark outline. Referee: small solid black diamond with a thin white outline.
- Pitch: dark desaturated forest green `#2E5A30` with very subtle mowing stripes running across the length, white lines at about 60% opacity. Lime green is reserved for the selected-player ring, trail and accents.
- Rating colors (pills, All ratings): below 5.0 red, 5.0 to 5.9 orange, 6.0 to 6.9 yellow, 7.0 to 7.9 light green, 8.0 and above strong green; the number is always visible. `Colorblind colors` (View popover, off by default) switches to blue-to-orange. Rating log deltas: green with `+`, red with `-`. The OVR label is neutral grey, never colored.
- `Activity labels` (checkbox in the PlaybackBar, off by default, remembered per viewer): shows each player's current activity from `positions.json` (`act`, looked up in `meta.activities`) as small text under every dot, with underscores as spaces ("hold shape", "track back", "jog"). Off: only the selected player's activity shows, plus the existing special labels such as "Celebrating". The referee has no label. Same look as the dev viewer.
- `Show ratings` (View popover, off by default) puts every player's rating pill above their dot; with it off only the selected player's rating shows, and a rating pop appears briefly when a rating changes.
- Brief fading action visuals: pass line, shot line with speed pop (for example "112 km/h"), tackle flash, pressure pulse, rating pop; banners for goals and penalties; a small "Celebrating" label under a scorer.

## Commentary, trace and audio

- Commentary lines carry `t`, `duration`, `player`, `type`, text and an audio URL. A line shows when `t` reaches its start; a new line replaces the old after its duration.
- Seeking to an uncached chunk: pitch and ratings jump at once; the panel shows "Preparing commentary" and resumes at the next line when the chunk arrives. Lines that arrive more than about 10 seconds late are dropped.
- **Above-1x rule (2x to 30x):** pitch, ratings and rating log keep running; commentary text and voice are off with the message "Commentary pauses at {rate}x speed" (`{rate}` is the current rate, so 2x shows "Commentary pauses at 2x speed"; 3x is not a valid rate) and a greyed speaker icon; the crowd stays on. No commentary requests are made while the rate is above 1; when the rate returns to 1x, fetch the chunk at the playhead plus the next one and show "Preparing commentary" until it arrives. Changing speed stops any clip that is playing.
- "How this was made" expands a compact vertical trace in the panel: Interpreter, Moments, Commentator, Fact Guard (amber badge and a before/after diff when it fixed something), Personalizer (mode and language), Voice (clip length). Data comes from `GET /agents/trace?line=<id>`. There is no agent strip anywhere else.
- Audio: Web Audio crowd loops (murmur always on; clip and volume chosen by event importance, Azure City is the home side) plus the commentary clips. The Start click unlocks audio; Mute is in the View popover.
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
- Browser storage is not needed for correctness; any use (for example the chosen language) is wrapped in try/catch.

## Open questions

- Whether to add a small minimum-distance nudge between dots if overlaps look bad (see Spec: Simulator Movement).
- Decided: the match picker lives in both the Start overlay and Match info (see the component tree).
