# Phase 2 handoff: Match Viewer (done Oct 26, 2026)

> Short orientation notes for the next phase's session: what exists, where, and what not to break. This is a summary, not a substitute: still read CLAUDE.md, PRODUCT.md, ARCHITECTURE.md, TASKS.md, `docs/decisions.md`, the specs your phase prompt lists, `docs/phases/phase-1.md` and the `docs/ui/` images. The specs win over this file.

## What was built

| Piece | Where |
| --- | --- |
| React + Vite + Tailwind + TypeScript app | `web/` (`npm run dev`, `npm test`, `npm run build`) |
| Contract types, generated (never hand-written) | `web/scripts/gen-types.mjs` -> `web/src/types/generated/`; re-exported from `web/src/types/index.ts` |
| Dev data serving: `/data/...` from repo-root `data/`, `GET /matches` | `web/scripts/match-data-plugin.ts` (Vite dev + preview only) |
| Match loading and lookups (positions as `Int16Array`, rating, score, cards, highlights, distance) | `web/src/lib/match.ts` |
| Playback clock `{t, playing, rate}` + hooks | `web/src/lib/clock.ts`, `web/src/hooks/useClock.ts` |
| EN/ES reason templates for all 34 codes | `web/src/lib/reasons.ts` |
| Commentary placeholder `getCommentaryChunk` + `getTrace` | `web/src/lib/commentary.ts` |
| Crowd audio: cue rules (pure, tested) and Web Audio playback; 8 CC0 clips (about 2 MB: four `.m4a` takes from a real stadium recording, three `.mp3`, a real referee whistle) with `CREDITS.md` | `web/src/lib/crowd.ts`, `web/src/lib/audio.ts`, `web/public/audio/crowd/` |
| Every frontend knob (speeds, spotlight, visuals, cadence, standings) | `web/src/lib/config.ts` |
| Components | `web/src/components/` (Pitch, PitchOverlays, PitchMarkings, ScoreBar, Banners, PlaybackBar, ViewPopover, HighlightsRow, Sidebar, PlayerCard, RatingChart, RatingLog, CommentaryPanel, AllRatings, StartOverlay, FullTimeCard, MatchPicker) |
| Goal reveal: shot flight and the time a goal is shown (`revealAt`, `goalRevealT`, `shownAt`, `shownScoreAt`) | `web/src/lib/match.ts` |
| Tests (41, Vitest, pure helpers only; run on the real hero files) | `web/src/lib/*.test.ts` |

## Key facts

- The pitch is drawn imperatively: React renders the SVG once per match and selection, and a clock frame listener writes `transform` and text on refs. Panels re-render at most about 10 Hz (`useMatchTime`) or once per match second (`useMatchSecond`). 60 fps at 30x on an M1.
- Ratings are read from `rating_after` (never recomputed). xG per shot, importance and positions come from the files; the frontend only sums xG and distance for the Analyst stat line.
- Hero highlights as shown: 12' Ribeiro, 18' YEL Visser, 22' YEL Weber, 23' YEL Pereira, 39' Lima, 51' RED Pereira (the second yellow is merged into the red), 54' PEN Thomas (award), 55' Thomas (kick), 77' YEL Santos, 88' Ribeiro, 89' Lima. Lima finishes 8.9.
- Spotlight: about 7 match seconds after a big moment (importance 0.8 or more) of the selected player, and 2.5 s after a click (owner, Oct 26: the dim is instant, then eases out: after a click it holds 1.5 s and fades back over 1 s; after a big moment it fades over the last 1.5 match seconds); otherwise nobody is dimmed.
- Commentary is off above 1x (no `getCommentaryChunk` calls), with "Commentary pauses at {rate}x speed".
- Layout: one row (pitch + sidebar) from `lg` (1024 px); below that one column. The pitch box sizes from container-query units: below `lg` its container measures width only (a `size` container with no definite height resolves to 0 and hides the pitch). The playback bar wraps by its own width (`@container`, `@2xl`), not the screen's, because the pitch can be narrow on a wide screen (phone landscape). Checked at 390x844, 844x390, 820x1180, 1280x800 and a 3432 px wide display.
- Owner changes after the first build (all in `docs/decisions.md` and `specs/frontend.md`): 14 px / 12 px type tiers and a 360/400 px sidebar; Mexican-Spanish wording; gold and pink goalkeepers; football-patterned ball at its true position; movement arrows (small triangle on the outline; lime for the followed player; white for the 5 nearest within 25 m; "All movement arrows" setting, off by default); Activity labels moved into the View popover and off for the followed player too; lime progress bar and switches; square-cornered pitch with 16 px page padding; team-coloured labels on All ratings; crowd audio (wordless CC0 murmur and reactions, real referee whistle; see Spec: Match Rules); grey thin scrollbars; shot flight (the ball flies a shot in ~0.4 s and the goal banner and score wait for it); football and penalty icons on the highlight chips; keyboard play (the pitch is one tab stop, arrows move between nearby players); screen-reader announcements for goals, cards and penalties. Later (Oct 26-27): stadium crowd clips (goal roar, near-miss "ooh", cheer, an anguished "OHHH" plus a hush for a Redmond goal); referee whistle 0.4 s before the crowd reacts and for every card and the penalty at every speed; reactions shortened in proportion to speed (at least 2.5 s); one Mute button, in the playback bar between play/pause and the clock (removed from the commentary panel and the View popover); full-screen button (pitch box only, black bars); control bar wakes only over the pitch, hides 1.5 s after the mouse stops, the cursor hides with it, and a mouse-clicked control never pins it open; on a narrow pitch the bar splits into a left group (play, mute, clock) and a right group (speeds, gear, full screen); measured tag widths; Start overlay as a full-screen modal below `lg`; rating log rows seek to 4 s before their change; the profile picture stays top-aligned in Analyst mode.
- **A goal is shown when its ball lands, not at the kick** (0.4 to 0.9 s later): score bar, GOAL banner, net flash, highlight chip, rating pops of that second, the GOAL commentary line, the crowd roar and the screen-reader announcement all use `goalRevealT` / `shownAt` from `web/src/lib/match.ts`. The shot line, xG chip and rating log stay on the kick.
- A dev-only `window.__playerLens` (`clock`, `select`, `audio()` for the crowd engine state and last cues) puts the app in any state for browser checks: `__playerLens.clock.seek(2330)`. Stripped from production builds. Chrome refuses fullscreen from automated clicks ("not granted"), so test full screen by hand.

## Rules for later phases

- **Phase 3 swaps two function bodies, not the callers:** `getCommentaryChunk(match, player, mode, lang, chunk)` becomes `GET /commentary?match&player&mode&lang&chunk` (handle the 202 `preparing` answer by returning nothing yet and retrying; the panel already shows "Preparing commentary" while a chunk is missing), and `getTrace(lineId)` becomes `GET /agents/trace?line=`. The panel already caches by (match, player, mode, lang, chunk) and fetches the playhead chunk plus the next.
- Phase 3 also fills the commentary clip player in `web/src/lib/audio.ts` (`playClip`, `stopClip`), and replaces the full-time recap template in `FullTimeCard.tsx` with `GET /recap`. The crowd is already built: there is no `crowdReact` any more. Play the voice through the same AudioContext and master gain as the crowd, so the one Mute button (in `PlaybackBar`) silences both, and duck the crowd under the voice with the `CROWD.duck*` knobs (35%, 60% under a goal roar, 0.2 s down, 1 s back; Spec: Match Rules).
- **Goal lines:** a commentary line whose `t` is a goal's second must show when the ball lands. The placeholder does this with `shownAt(match, e.t)` in `buildLines`; real backend lines need the same, so apply `shownAt` where lines are shown (or have the backend emit the reveal time) rather than at the kick.
- **`/audio` is shared:** the crowd clips are static files at `/audio/crowd/*` (from `web/public`, later `web/dist`); commentary clips are `/audio/<hash>.mp3` from FastAPI. A dev proxy or a FastAPI mount for `/audio` must leave `/audio/crowd/` alone (for example the Vite proxy key `^/audio/(?!crowd/)`), or the crowd goes silent with 404s.
- FastAPI must serve the same URLs the dev plugin does: `/data/matches/<id>/*.json` and `GET /matches` (shape in `specs/agents-backend.md`), and `web/dist` for the app (Phase 4).
- After any change to `contracts/`, run `npm run gen:types` in `web/`.
- Don't move dot positions anywhere but the frame listener in `Pitch.tsx`, and don't compute numbers the files already have.

## Data traps (frontend side)

- `shape_check` events (half the file) are filtered out at load; rating entries with `delta` 0 are dropped from the log.
- A goal is a `shot` and a `goal` at the same `t`: banners, chips and score use the `goal` event; the shot line and km/h pop use the `shot`.
- The penalty is two events: `penalty` (award, outcome `awarded`) at 53:47 and the kick (`shot`) at 54:22; the PENALTY banner follows the award, the xG chip stays until the kick.
- The sent-off dot fades once it stops on the touchline (`sentOff.stopT`, found from the positions).
- Chrome throttles requestAnimationFrame for a hidden or occluded window; the clock caps one frame step at 0.25 s so a background tab doesn't jump the match. Playback looks slow in a background tab; that's expected.

## Not done (with reason)

- Spoken commentary: no Speech output exists yet (Phase 3); `playClip` / `stopClip` and the Mute button are wired. The crowd is built.
- Full screen: the real fullscreen request was never triggered in automation; the fullscreen layout was checked by applying the same styles by hand. The four `.m4a` crowd clips may not decode in Firefox on Linux without system AAC codecs (those reactions then stay silent; nothing else breaks).
- Agent trace steps other than `Template`, the Fact Guard badge and diff: they need real traces from Phase 3; the trace view renders any step list from the contract.
- "Preparing commentary" for a slow network and the 10 s late-line drop are implemented but only exercised with the instant local placeholder.
- Minimum-distance nudge between overlapping dots: still an open question in the spec; not built.
- A highlight for the ball carrier: left out (the football on their dot already marks them); easy to add if it is hard to follow.
- Not checked by hand: a real screen reader (NVDA, VoiceOver) and Safari or Firefox. Only Chrome was used; the ARIA structure was checked in code and with real key presses.

## How to run

```bash
cd web
source ~/.nvm/nvm.sh && nvm use 22   # Node is not on Claude Code's default PATH
npm install
npm run dev        # http://localhost:5173
npm test           # 41 helper tests
npm run build      # tsc + vite build into web/dist
```

The Python side is unchanged: `pytest` from the repo root still runs the 68 Phase 1 tests.

## Open items handed on

- Phase 3: the Spanish is Mexican football usage (see `docs/decisions.md`); pick an `es-MX` Azure AI Speech voice and use the same terms in the Spanish prompts and the Fact Guard verb tables.
- Owner: read the draft EN/ES reason templates in `web/src/lib/reasons.ts` (specs/match-files.md left them to the frontend build).
- Phase 3: real commentary, trace, recap and audio behind the existing functions.
- Phase 4: serve `web/dist` and the data routes from FastAPI.
