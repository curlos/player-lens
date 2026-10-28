# Spec: Rating Model

Oct 24, 2026 · @Carlos Martinez

> Detailed rating rules moved out of PRODUCT. PRODUCT holds the summary; this file holds the numbers. All values are starting points to tune against simulator output.

Starts at 6.0. Code computes every number; the LLM only rephrases the explanation. Every player gets a logged entry at least every 30 to 45 seconds, even if it is "no change".

## Actions and deltas

| Action | Delta | What counts |
| --- | --- | --- |
| Goal | +1.0 | Ball crosses the line |
| Assist | +0.6 | Last pass before a goal |
| Key pass | +0.2 | Pass that directly creates a shot |
| Shot on target | +0.15 | Heads into the goal frame and is saved or scores. Bar, post and wide shots are off target; a shot blocked by an outfield player is a block |
| Missed big chance | -0.3 | Shot with xG of 0.25 or more that misses, or hits the post or bar |
| Tackle | +0.15 | Wins the ball off an opponent who has it |
| Interception | +0.12 | Cuts out a pass between two opponents |
| Block | +0.2 | Outfield player stops a shot or pass with his body |
| Clearance | +0.08 | Defender under pressure near his own goal kicks or heads the ball away (out of play or to anyone). It removes the danger even if the opponent gets the ball afterwards |
| Aerial duel won | +0.08 | Two opponents contest a ball in the air (long ball, cross, goal kick, corner) and he wins it. An uncontested header does not count. The kickoff is not a duel |
| Dribble won | +0.1 | The player with the ball beats an opponent and keeps the ball |
| Beaten by dribble | -0.04 | The defender who was beaten |
| Foul won | +0.05 | Gets fouled |
| Pressure regain | +0.12 | Pressures the carrier and the team wins the ball back within 5 s |
| Counterpress | +0.15 | Pressures within 5 s of our own turnover |
| Recovery run | +0.15 | Sprints back goalside after our turnover; every player who does it is credited |
| Marking denial | +0.05 per window, capped at +0.3 | Stays tight so the opponent is not passed to |
| Decoy run | +0.1 | Run without the ball that drags a defender and frees a teammate |
| Shape check | -0.05 to +0.05 | Every 30 to 45 s: position vs formation slot, work rate, tracking back. May log "no change" |
| Dispossessed | -0.08 | Opponent takes the ball off him. Pairs with the other player's Tackle |
| Foul committed | -0.1 | Fouls an opponent (minor, reckless or violent) |
| Handball | -0.15 | Rare. Ball hits his hand or arm; a penalty kick is awarded only if a defending-team player commits a direct-free-kick offence in their own penalty area |
| Offside | -0.05 | Receiver caught offside |
| Yellow card | -0.3 | Cautioned |
| Red card | -1.5 | Sent off (straight red, or second yellow) |
| Error leading to goal | -1.0 | His own clear mistake (lost ball in a dangerous spot, failed clearance, lost mark) followed by an opponent goal within about 10 s. Can come from an off-ball failure. If several players erred, the last error gets -1.0 and up to two earlier ones get -0.3 each |
| GK save | +0.1 + 0.8 x xG, capped at +0.6 | Stops a shot on target. The harder the shot (higher xG), the bigger the credit |
| GK claim or punch | +0.1 | Catches (claim) or punches away a cross or high ball |
| GK sweep | +0.12 | Leaves his line to clear or collect a ball played behind the defense. Hands only inside his own box; outside it he plays with his feet |
| GK goal conceded | -(0.2 + 0.7 x (1 - xG)) | Shot on target beats him. A routine shot (xG 0.05) costs about -0.87; an unstoppable one (xG 0.8) about -0.34 |

## Rules

- Soft cap: gains shrink near the top, effective delta = delta x min(1, (10 - rating) / 3). Losses shrink near the bottom the same way, min(1, (rating - 3) / 3). At 9.5 a goal adds +0.17 (9.7); at 8.5 it adds +0.5. Each log entry stores the raw delta, the scale factor and the final change.
- Display: one decimal, never exactly 10.0 or 3.0 (range 3.1 to 9.9), so ratings look like real ones (9.7, 9.8).
- Repeat decay: the same action earns less each time.
- Standing, walking and jogging never change a rating by themselves. Commentary can still describe them ("holding the line", "drifting into the pocket"). Walking while out of position when the team presses is a shape-check negative.
- "No change" shape checks are logged but silent; the commentator does not announce them.
- No provisional period. A rating moves from the first action, and a goal changes it instantly.
- Explanations are templates written by code (same event, same text). The commentator agent then adds a personal voice on top of that factual log; any LLM rewording is optional.
- Off-ball definitions follow the StatsBomb glossary: a counterpress is a pressure within 5 seconds of our own turnover; a pressure regain is the ball won back within 5 seconds of that pressure.
- These started as guesses; a first tuning pass is in `rating/config.py` and the owner accepted it as final for the hackathon (Oct 26). Ratings run slightly high (mean about 7.0).

## Chance quality (xG)

xG (expected goals) is the probability that a shot becomes a goal. Code computes it from:

- Distance to goal: farther is harder.
- Angle to goal: straight on is easier; from near the byline or corner is much harder.
- Defender pressure: how many defenders are near the shooter and whether any stand in the shot line.
- Shot type: foot or header (headers are harder).

Bands: under 0.05 low, 0.05 to 0.25 medium, 0.25 or more big chance. Goalkeeper position is not part of xG. xG feeds the shooter's rating, the keeper's save and conceded values, and the missed-big-chance penalty.

## Event importance and commentary tone

Every event gets an importance score from 0 to 1, computed by code: a base weight by event type (goal 1.0, red card 0.9, big save 0.7, key pass 0.3, routine pass about 0.05), times context (late in the match, score close, title decider, involves the selected player), nudged by the size of the rating change.

- 0.8 or more: ecstatic, longer line.
- 0.4 to 0.8: lively.
- 0.15 to 0.4: calm, short.
- Under 0.15: filler only, used for quiet-spell lines after 25 s with no line (see ARCHITECTURE, Commentary cadence).

The commentator gets the tone and the facts; it does not decide how important something is. Importance also picks crowd clips and volume.
