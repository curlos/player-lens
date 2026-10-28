# Spec: Match Rules, Reactions and Audio

Oct 24, 2026 · @Carlos Martinez

> Detailed simulator behavior, player activities, group reactions and audio, moved out of PRODUCT. PRODUCT holds the summary.

## Match rules: referee, fouls and restarts

- A referee marker follows the ball at a distance: a small solid black diamond with a thin white outline (not a circle, no number, no rating), so it never reads as a player or the ball. Players are large team-colored circles with numbers; the ball is a small white dot. For a card, the player walks up to the referee, a yellow or red card icon pops next to both, and a line appears in the commentary. Dissent plays the same way: the player runs to the referee and stands next to him for a couple of seconds before the card.
- Fouls are simulated. Severity: minor (free kick), reckless (yellow), violent or stopping a clear goal chance (red). A second yellow is a red. Handballs are rare but possible.
- Foul chance depends on a fictional temperament trait (calm, normal, hot-headed), Defending skill and the team's press level. A player on a yellow card takes fewer risks unless he is hot-headed. Hot-headed players can also be booked for dissent (arguing). Traits are not copied from real players.
- Set pieces (all in scope): kickoff, throw-in, goal kick, corner, free kick, penalty kick. Each has a simple dot layout, for example a wall and box positions for a free kick, and all 22 players visible for a penalty (kicker and keeper alone, everyone else outside the box).
- Award a penalty kick only when a defending-team player commits a direct-free-kick offence in their own penalty area. Other offences in the penalty area do not result in a penalty. It is a single spot kick inside a league match, not a shootout.
- Set-piece takers: each team has a designated penalty and free-kick taker, chosen by code as the best on-pitch player on a new attribute, Set pieces (1-99, covers penalties and free kicks), with Finishing and Composure as tie-breakers. The fouled player does not take it. Stars usually take them because they rate highest. If the taker is sent off, the next best takes over.
- Penalty outcome: about 75 to 80 percent conversion on average, shifted by the taker's Set pieces and Composure against the goalkeeper's Shot-stopping. Free kicks near the box can be a direct shot (xG from distance and angle) or a pass into the box.
- Offside is simulated in its basic form: at the moment a teammate passes, a receiver in the opponent's half who is closer to the goal line than both the ball and the second-last defender is offside. Result: an indirect free kick to the defending team and a -0.05 rating for the receiver. Azure's high defensive line should catch more players offside than Redmond's deeper block. Cut it if the simulator runs late (cut order: red cards, then offside).
- A red card means that team plays with 10. One formation slot drops (4-4-2 becomes 4-4-1) and the simulator counts players on the pitch instead of assuming 11. Cards stay in scope. If the simulator runs late, red cards are cut first and yellows stay.

## Player activities (no rating effect)

Every player has exactly one activity code per second, saved with his position. Activities never change a rating by themselves, but the commentator can describe them and the shape check reads some of them.

| Code | Meaning |
| --- | --- |
| stand, walk, jog, run, sprint | Movement state, set by speed |
| carry | Moving with the ball |
| press | Closing down the ball carrier |
| track\_back | Running back toward his own goal |
| mark | Staying with an opponent |
| make\_run | Off-ball run forward (can become a decoy run) |
| hold\_shape | Keeping formation position |
| talk\_ref | Next to the referee (dissent or a complaint) |
| huddle | Teammates gathering (before a set piece, around a scorer or an injured player) |
| celebrate | After scoring |
| down | On the ground after a foul or injury, for a few seconds |
| wall | In a free-kick wall |
| set\_piece\_wait | Waiting outside the box at a corner or penalty |
| take\_set\_piece | Taking the corner, free kick or penalty |
| sent\_off | Sent off: walks to the bottom touchline (y = 68, 7.5 m left of halfway for Azure, right for Redmond) and stays there, so positions stay on the pitch and clear of the score bar (added in the build) |

Events (things that can change a rating) have their own codes, such as pass, shot, goal, save, tackle, foul and pressure\_regain.

## Group reactions

- **Crowding the referee:** after a red card, a bad call or a disputed goal, 1 to 3 nearby teammates walk to the referee (talk\_ref). He never reverses the call. More likely after harsh decisions and with hot-headed players. The referee gets a rare call wrong (about 3 percent of decisions), which is what starts arguments.
- **Injury:** rare (about one per match, none in the hero match). The player goes down for 5 to 10 s, 2 to 3 nearby players walk over, play stops, then he carries on. No substitutions.
- **Goal celebration:** the scorer runs toward a corner and celebrates for 6 to 8 s. The assister joins first, then 3 to 5 teammates, then everyone resets for the kickoff. The star can have one small signature move, such as a jump.

## Crowd sound

Eight wordless CC0 recordings from Freesound (murmur, roar, cheer, "ooh", an anguished "OHHH", gasp, boos, a real referee whistle; credits in `web/public/audio/crowd/CREDITS.md`) played through the browser's Web Audio. The murmur, goal roar, near-miss, conceded-goal "OHHH" and cheer are takes from one real football stadium recording, so the crowd sounds like a stadium; each take must be wordless (owner checks by ear), so no real club, chant or language is heard. Built in Phase 2 (owner, Oct 26). Azure City is the home crowd. Code: `web/src/lib/crowd.ts` (pure cue rules, tested) and `web/src/lib/audio.ts` (playback); every volume and timing is a knob in `CROWD` and `CROWD_CLIPS` in `web/src/lib/config.ts`.

| Moment | Azure | Redmond |
| --- | --- | --- |
| Goal (when the ball lands, `goalRevealT`) | roar | anguished "OHHH", then the home crowd goes quiet (murmur at 35% for 10 s, easing back) |
| Shot saved, missed or blocked | "ooooh... aww", louder with importance | nervous gasp from importance 0.4 |
| Penalty awarded | whistle + cheer | whistle + boos |
| Yellow card | whistle + boos | whistle + cheer |
| Red card | whistle + long loud boos | whistle + long loud cheer |
| Kickoff | whistle | whistle |
| Full time | three whistle blasts, murmur fades out | |

- The murmur is always on and swells as the ball nears a goal, more when Azure attack.
- A second yellow merged into a red reacts once (as the red); two decisions in one second share one whistle. Fouls and offsides don't whistle (owner, Oct 26: about 30 a match made it a constant peep).
- Each clip starts where its sound rises, so the loud part lands about 0.3 to 0.8 s after the moment; levels are matched per clip (`norm`).
- Seeking plays nothing for the skipped events and fades out reactions still sounding. Pausing silences everything (the audio context is suspended). At 10x and 30x only goals and red cards draw a crowd reaction, but the referee still whistles every card and the penalty; the murmur stays on at every speed. For cards and the penalty the whistle sounds first and the crowd answers 0.4 s later (`CROWD.afterWhistleS`). Above 1x each reaction is shortened in proportion to the speed (12 s roar: 6 s at 2x, 3 s at 4x), never below 2.5 s, at its normal pitch (owner, Oct 26).
- Mute (the speaker button in the playback bar, between play/pause and the clock) silences the crowd, and the commentary voice from Phase 3. The Start click unlocks audio; the clips load in the background after it, so the replay never waits.
- Commentary on top (Phase 3): **no ducking** (owner, Oct 27: lowering the crowd under the voice broke the immersion). The `CROWD.duck*` knobs stay in config at 1 (no drop). Instead the whole crowd sits at a steady `CROWD.crowdLevel` of 0.6 so the voice is easy to hear, and the voice itself gets louder with the ball near a goal (`voiceDangerBoost`) and on big lines (`voiceBigBoost`), through a limiter. A new line waits for the clip that is playing (dropped if it waited more than `voiceQueueMaxS`, 6 s); only a big line cuts in.
- No ball-kick sounds: about 900 passes a match would be a constant tapping at high speed and would compete with the commentary voice.

## Spoken commentary

- Commentary is spoken as well as shown as text, using Azure AI Speech text-to-speech (free tier 0.5 million characters a month; check the pricing calculator for pay-as-you-go).
- A Voice Director agent takes each finished line and its tone (calm, lively or ecstatic, from the importance score) and adds speaking instructions: pauses, emphasis, speed, and a voice style where the chosen voice supports one. Text-to-speech then renders the audio.
- Everything is pre-generated and cached. Visitors never trigger synthesis.
- Voice the default star first, in English and Spanish and both modes (about 1,800 lines, about 216,000 characters, at the decided commentary cadence). Add a few more players in English if budget allows. Everyone else stays text, with the browser's built-in voice as a free fallback.
- Each clip starts at its moment's timestamp. If an earlier clip is still playing, a lower-importance line is skipped. Lines must be short enough to finish before the next one.
- Pick the voice after testing two or three; style support varies by voice.
- The crowd sits quietly behind the commentary at all times.
