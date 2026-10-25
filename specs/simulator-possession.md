# Spec: Simulator Possession and Decisions

> How the player with the ball decides what to do and whether it works. All formulas and numbers are starting guesses to be calibrated against the benchmark table (ARCHITECTURE section 3); keep every knob in one config file. Related: Spec: Simulator Movement, Spec: Rating Model, Spec: Match Rules, Reactions and Audio.

## Scope

- Covers possession state, the carrier's decision, the outcome roll and the events produced.
- Movement of everyone else is in Spec: Simulator Movement; ratings are computed afterward by the rating engine from the events.
- Deliberately simple: a short option list scored by a formula, logistic outcome rolls, seeded randomness. No learning, no search.

## Possession state

The ball is always in one of three states:

- **Carried:** a carrier has it, positioned about 0.5 m ahead of them.
- **In flight:** a pass, shot or clearance with a start, a target point, a speed and an intended receiver (if any).
- **Loose:** nobody controls it; it moves with decaying speed until someone wins it.

A carrier does not act every second. After gaining the ball they carry; a decision is made about every 2 to 4 seconds (`decision_interval`, shorter under high pressure or high team tempo), or immediately when pressured within about 2 m.

## Step 1: build the option list

The carrier considers:

| Option | Candidates |
| --- | --- |
| Pass | Each teammate within pass range and not behind a blocked lane (up to about 6, more with high Vision) |
| Dribble | Forward and one or two diagonal directions |
| Shoot | Only inside shooting range (about 30 m) and with an angle; considered when xG is at least a small threshold |
| Clear | Only in own defensive third under heavy pressure |
| Carry | Keep the ball and move toward the carry target |

## Step 2: score and choose (decide)

Each option gets a score; the highest scores are the candidates and one is chosen with seeded randomness (softmax with a temperature that falls as Composure rises).

- **Pass score** = progress toward goal (meters gained) x forwardness weight + receiver openness (distance to the nearest defender) - pass difficulty - risk (opponents near the lane) + receiver quality bonus. Team style shifts it: direct play raises the forwardness weight, patient play raises the openness weight.
- **Dribble score** = space ahead - number of nearby defenders + Dribbling bonus.
- **Shoot score** = shot xG x shot weight, boosted when the chance is a big chance (xG 0.25 or more).
- **Clear score** = safety (distance from own goal and opponents) when pressure is high; otherwise zero.
- **Carry score** = a small baseline, higher with open space ahead.
- **Vision** widens how many pass candidates are considered and sharpens the scoring; **Composure** reduces the penalty of pressure on the choice; **tempo** and **style** bias between safe and direct options.

Pressure is the number and closeness of opponents within about 3 m of the carrier, weighted by their `press_intensity`.

## Step 3: resolve the outcome (execute)

Success probability is a logistic function: `p = 1 / (1 + exp(-(base + attribute terms - distance term - pressure term - difficulty term)))`. Coefficients are guesses, calibrated until the match totals sit in the benchmark bands.

| Action | Outcomes | Main drivers |
| --- | --- | --- |
| Pass | complete, intercepted (by the best-placed defender in the lane), misplaced (goes loose or out of play) | Passing, Composure, distance, pressure, difficulty; interception uses the defender's Positioning and Defending |
| Dribble | beats the defender, loses the ball, fouled | Dribbling vs the nearest defender's Defending; Pace difference |
| Shot | blocked, off target, saved, goal | Finishing, Composure, xG (distance, angle, pressure); then goalkeeper `gk_shot_stopping` vs shot quality for save or goal |
| Tackle | wins the ball, misses, foul | Defending and press intensity vs Dribbling; a defender within about 2 m of the carrier and pressing may attempt one |
| Clearance | clears, or is blocked | Defending, pressure |
| Aerial duel | won or lost | Strength |
| Loose-ball contest | winner is the first to arrive, with ties broken by Strength | Pace, distance, Strength |

Penalties and free kicks follow Spec: Match Rules, Reactions and Audio (the best Set pieces player takes them; penalty conversion about 75 to 80 percent).

## Step 4: apply the result

- New carrier, loose ball, ball out of play (a restart event), foul (free kick or penalty, possibly a card), or a goal (kickoff).
- Interception, tackle win and loose-ball win by the defending team start a possession; the first events after a turnover can count as counterpress or pressure regain (see Spec: Rating Model for the exact definitions).
- Every result is logged as an event with a unique ID (`ev_####`), time, type, player(s), from/to coordinates, outcome, xG where relevant, and an `importance` score (0 to 1) computed by code.

## Chance quality (xG)

Computed from distance to goal, shot angle, defender pressure and shot type. Bands: under 0.05 low, 0.05 to 0.25 medium, 0.25 or more big chance. Used by shot decisions, goalkeeper save probability and the rating engine.

## Invariants (testable later)

1. Same seed gives byte-identical events.
2. Every event has a unique ID and a time inside the match.
3. Exactly one ball state at any time; a carried ball is always with a player on the pitch.
4. Ball speed never exceeds about 30 m/s.
5. Outcomes are drawn only from the explicitly passed RNG.
6. Over many seeds, match totals land in the benchmark bands: passes 850 to 940, completion 82 to 84 percent, shots 22 to 25, goals 2.5 to 3.0.

## Tuning knobs (one config file)

Decision interval, pass range, option counts, scoring weights (forwardness, openness, risk, shot weight), softmax temperature, shooting range and xG threshold, every logistic base and attribute coefficient, pressure radius and weighting, foul chance per tackle, penalty conversion.

## Calibration order

Tune one knob at a time: tempo (pass volume), then pass interception, then shot propensity, then the xG intercept (goals). Check that goals per team look roughly Poisson and that Azure's high press produces more pressures and distance than Redmond.

## Open questions

- Final attribute list: confirmed Oct 24 (see ARCHITECTURE).
- Vision is a separate attribute; Anticipation is folded into Positioning (decided Oct 24).
