# Spec: Simulator Movement

> How the simulator moves players, referee and ball every second. All numbers are starting guesses; keep every knob in one config file so it can be tuned. Related: ARCHITECTURE section 3 (invariants), Spec: Match Rules, Reactions and Audio.

## Scope

- Decides where the 22 players, the referee and the ball are at each second of the match (about 5,400 ticks).
- Does **not** decide actions (pass, shot, tackle) or their outcomes; that is the possession and decision model and the action resolver. Movement reads their results (who has the ball, where it goes) and moves everyone else around them.
- Deliberately skipped: pathfinding and collision physics. Players walk straight to their target and may briefly overlap; duels are dice rolls from attributes.

## State and tick

- One tick = 1 second (`dt = 1`). Positions are recorded every tick.
- Per player: `pos` (m), `vel` (m/s), `fatigue` (0 to 1), `activity` (label), `target` (m).
- Order inside a tick: (1) action model updates possession and the ball, (2) every player picks a target, (3) every player moves via `move_player()`, (4) fatigue updates, (5) activity labels are assigned, (6) referee and ball move, (7) record the snapshot.
- Order of players is fixed (by team, then shirt number) and the RNG is passed explicitly, so the same seed gives identical output.

## Step 1: pick a target

| Situation | Target |
| --- | --- |
| Base | Formation slot (normalized 0 to 1, from the config map `FORMATION_XY[formation][shirt_number]`) converted to meters; mirror for the away side |
| Team shape | Whole team shifts toward the ball. x shift = about 30% of the ball's offset from the team's center; y shift about 25%. Then scaled by the team's `def_line` (how high the back line sits), `width` and `tempo` |
| Our team has the ball | Shape pushes up toward the opponent half; forwards and wide players run into space ahead of the ball (`make_run`); wingers hold the touchline; midfielders offer passing lines near the carrier |
| Opponent has the ball | Shape drops and compacts toward our goal; the nearest defenders press; others mark or hold the line |
| Pressing | The nearest 1 to 2 players to the ball carrier (2 when `press_intensity` is high) within a trigger distance (about 15 to 25 m, scaled by press intensity) target the carrier's predicted position 1 s ahead. Press intensity also sets how long they keep pressing before dropping off |
| Marking | Each defender not pressing is assigned the nearest unmarked opponent in their zone; target is a point 1.5 to 2 m goal-side of that opponent |
| Recovery run (`track_back`) | If our player is beyond the ball line, the opponent has the ball and the player is more than about 15 m from their slot, target is their slot at sprint speed |
| Ball carrier | Target is the carry point chosen by the decision model (toward goal, space or a teammate) |
| Goalkeeper | Stays between the ball and the goal center, within about 12 m of the goal line, y tracking the ball clamped to a little wider than the goal; steps out when a through ball is likely |
| Restarts (kickoff, throw-in, goal kick, corner, free kick, penalty) | Fixed layouts from Spec: Match Rules, Reactions and Audio; players walk or jog to them |
| Red card | The player leaves the pitch; the team's formation drops one slot and the simulator counts players on the pitch, never a fixed 11 |

Offside awareness: forwards making runs do not target a spot beyond the second-last defender unless the run is timed with a pass (the action model decides).

## Step 2: `move_player()` (the only code that changes positions)

- `max_speed = min(9.0, 7.0 + 2.0 x pace / 99)` m/s, reduced by fatigue: `max_speed x (1 - 0.25 x fatigue)`.
- Desired velocity points at the target. Desired speed is capped by `max_speed` and by a braking limit, `sqrt(2 x accel x distance)` (the fastest speed from which the player can still stop at the target using the same `accel`), so they slow down early instead of overshooting. The older `distance / dt` cap is kept as a last-tick safety.
- Acceleration limit: the velocity change per tick is at most `accel x dt`, with `accel = (2.5 + 2.0 x pace / 99) x (1 - 0.25 x fatigue)` m/s^2: the Pace-based value, reduced by the same fatigue factor as `max_speed` (there is no separate Acceleration attribute; decided Oct 24). Every `accel` used in this spec (braking cap, applied-velocity cap, arrival, invariants) is this fatigue-adjusted value. The limit always wins over the speed caps above.
- Applied-velocity cap (normal approach): the speed caps above only shape the desired velocity, and the acceleration limit can leave the applied velocity higher than desired, which would carry the player past the target. So each tick, with distance `d` to the target, current speed `v` and step `a = accel x dt`, the applied speed must also satisfy the discrete stopping rule: `v_new x dt + stop(v_new - a) <= d`, where `stop(u)` is the distance covered while braking in steps of `a` from speed `u` to 0 (about `u x (u + a) / (2 x accel)`, summed per tick). The largest such `v_new` is the cap (a short loop or closed form is fine). The applied speed is then `max(min(desired speed, cap), v - a)`: the player takes the cap when it is reachable, otherwise brakes as hard as the acceleration limit allows. The velocity change stays a vector limit and nothing is snapped, so a player who can stop in time lands on the target without crossing it. When even full braking cannot avoid crossing (the target moved), the unavoidable-overshoot rule below applies unchanged.
- Arrival: when the player is within `arrival_radius` (about 0.5 m) of the target and their speed is at most `accel x dt`, they stop on it (velocity 0), which respects the acceleration limit. This stops dots from jittering around a formation slot.
- Unavoidable overshoot (the target changes suddenly, for example a press or a turnover): the player is never teleported or snapped back. The velocity change limit applies to the whole velocity vector, so they brake along their current heading first and then turn back; a reversal therefore takes several ticks and cannot flip direction every tick. Each tick they apply the same braking cap against the new target.
- New position = old position + applied velocity x dt, where the applied velocity is the one that already passed the acceleration limit and the applied-velocity cap above (never the raw desired velocity), then clamped to the pitch. Players never leave the pitch (the ball may, for throw-ins, corners and goal kicks, as explicit events).
- Typical speeds for reference: walk 1 to 2, jog 2 to 4, run 4 to 7, sprint 7 to 9 m/s. A 35 m run takes about 3.5 to 4 s.

## Step 3: fatigue

- Each tick: `fatigue += k x (speed / max_speed)^2 x load` where `load` rises with Work rate and the build rate falls with Stamina; `fatigue` recovers slowly when walking or standing.
- Fatigue reduces top speed and acceleration proportionally (see above). It carries across the whole match, so late-match players are visibly slower.

## Step 4: activity labels (one per player per second, never rated)

From speed and intent: `stand` (under 0.5 m/s), `walk`, `jog`, `run`, `sprint`; overridden by intent when relevant: `press`, `track_back`, `mark`, `make_run`, `hold_shape`, `carry`, plus the set-piece and reaction labels from Spec: Match Rules, Reactions and Audio. Activities feed commentary and animations and are used to detect off-ball work (pressure, recovery run, marking denial, decoy run); they never change a rating by themselves.

## Referee and ball

- **Referee:** target is the ball position offset about 10 to 15 m toward the center of the pitch; max speed about 5 m/s; never stands on a play. Rendered as a small solid black diamond with a thin white outline.
- **Ball:** carried (about 0.5 m ahead of the carrier) or in flight or loose. Flight speed and direction come from the action resolver (pass, shot, clearance); a loose ball decays in speed. Ball speed is capped at about 30 m/s.

## Invariants (testable later)

1. Same seed gives byte-identical output.
2. Displacement per tick is at most `max_speed x dt` (no teleporting); speed never exceeds 9 m/s.
3. Velocity change per tick never exceeds `accel x dt`.
4. Every player stays inside the pitch; the ball stays inside except on explicit restart events.
5. Positions change only inside `move_player()`.
6. Exactly the right number of players on the pitch (11, or fewer after a red card).

## Tuning knobs (one config file)

Formation slot coordinates (`FORMATION_XY`, keyed by formation and shirt number), team tactics (`TEAM_TACTICS`, keyed by team id: `press_intensity`, `tempo`, `width`, `def_line` as 0 to 1 floats, and `style` as `direct`, `balanced` or `patient`; starting guesses with Azure higher on press and line, Redmond deeper), ball-shift factors (x, y), trigger distances for pressing, number of pressers per press intensity, marking offset, recovery-run distance threshold, base and Pace-scaled speed, acceleration constants, arrival radius, fatigue constant `k` and the work-rate and stamina multipliers, referee distance and speed.

## Open questions

- Add a small minimum-distance nudge between players if overlapping dots look bad on screen.
- Use 0.5 s internal ticks (recording every second) if 1 s steps look jerky.
- Acceleration is derived from Pace (decided Oct 24).
