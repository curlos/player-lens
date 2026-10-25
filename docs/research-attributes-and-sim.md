# Research: EA FC and Football Manager lessons for Player Lens attributes and the Monte Carlo simulator

Oct 24, 2026 · @Carlos Martinez

> Reference for the simulator and rating work. Written Oct 24, 2026 from public sources. Coefficients are starting guesses to be calibrated, not facts. Some benchmark figures are from secondary or aggregator sources (flagged in Caveats).

## TL;DR

- **Attributes:** keep the 1-99 scale. Expand to 12 outfield attributes: Pace, Acceleration, Passing, Vision, Finishing, Dribbling, Tackling, Anticipation, Composure, Strength/Aerial, Work rate and Stamina. Add two goalkeeper attributes: Shot-stopping and Command. Each should map to one or two specific event probabilities or off-ball actions credited in the rating. **If time is short, add only Composure, Strength/Aerial and GK Shot-stopping** (this is what `sim/models.py` currently has).
- **Engine:** logistic functions for pass success (distance, pressure, passer skill), a distance-plus-angle logistic xG for shots, and stamina-driven decay of speed and acceleration. Don't simulate final scores with a Poisson model; use Poisson/Dixon-Coles only as a sanity check on the scoreline distribution across seeds.
- **Calibration:** run 200+ seeds and tune intercepts in a fixed order (tempo -> pass volume, pass intercept -> completion %, shot propensity -> shots, xG intercept -> goals) until means fall inside the benchmark bands.
- **IP:** copying the concept of face stats, sub-attributes and roles is fine (copyright doesn't protect game mechanics). Don't copy EA's data, real player ratings, or branded names like "PlayStyles".

## 1. How EA FC / FIFA models players

**Structure (official, visible in-game).** Every outfield card shows six face stats: PAC, SHO, PAS, DRI, DEF, PHY. Each is a weighted average of underlying sub-attributes. FIFA 16 had 28 specific attributes. Reactions feeds no face stat but counts toward overall rating. Groupings:

- **PAC:** Acceleration, Sprint Speed
- **SHO:** Finishing, Long Shots, Shot Power, Attacking Positioning, Penalties, Volleys
- **PAS:** Short Pass, Vision, Crossing, Long Pass, Curve, FK Accuracy
- **DRI:** Dribbling, Ball Control, Agility, Balance
- **DEF:** Marking, Standing Tackle, Interceptions, Heading Accuracy, Sliding Tackle
- **PHY:** Strength, Stamina, Aggression, Jumping

FC 26 guides label the DEF group as Defensive Awareness, Heading, Interceptions, Standing Tackle and Sliding Tackle, and list goalkeepers with a separate GK block.

**Face-stat weightings (community-reverse-engineered, FIFA 16 era; EA has not published them):**

- Pace: Sprint Speed 55%, Acceleration 45%.
- Dribbling: Dribbling 50%, Ball Control 35%, Agility + Balance 15%.
- Passing: Short Pass 35%, Long Pass 15%, rest spread over the other four.
- Shooting: Penalties only 5%.
- Physical: Strength 50%, Stamina 25%, Aggression 20%, Jumping 5%.
- Defending: fairly even, only a 20% spread between lowest and highest weight.

**Overall rating (community-reverse-engineered).** OVR = ATT + IR. ATT is a position-specific weighted average that includes only attributes relevant to that position (a centre-back's Vision contributes nothing). IR is an International Reputation bonus (3 star: +1 if base > 50; 4 star: +1 for base 34-66, +2 for 67+; 5 star: +1 for 29-49, +2 for 50-74, +3 for 75+). Penalties, Curve and FK Accuracy count toward no position's OVR. "Exact formula" calculators online are unverified.

**Lesson for Player Lens.** The live rating should be position- and role-weighted, like OVR, and can show its own breakdown. The reputation bonus is a non-performance fudge; don't include anything like it.

**Work rates -> roles (official).** EA's FC 25 FC IQ pitch notes state Work Rate and Player Instructions were replaced; Player Roles replace Work Rates. According to fifauteam.com, FC 26 has 37 Player Roles and 71 role-and-focus combinations, defining how each player behaves off the ball. So: treat Work rate as a capacity (how often and hard a player presses or recovers) and the archetype as the behaviour (where they go).

**PlayStyles (official).** PlayStyles replaced the old Traits system; PlayStyle+ is the stronger tier.

- FC 26 launch: removed Power Header, Aerial, Trivela and Flair; added Enforcer, Aerial Enforcement, Precision Header, Gamechanger and Inventive (35 total). EA said the gap between top-tier attributes and PlayStyle effects was too wide and rebalanced so high attributes perform core mechanics without the PlayStyle.
- FC 26 Title Update 1.5.0: high Short Pass, Long Pass and Curve can curve through balls without the Incisive Pass PlayStyle.
- FC 27 Gameplay Deep Dive (29 July 2026, Principal Gameplay Designer Gilliard Lopes): Low Driven shot velocity scales purely on core shooting attributes and input power; non-PlayStyle players with high Interceptions get more reach; Quick Step was cut back to give more importance to Acceleration; new off-balance dribbling is driven by Balance, Agility and Dribbling.
- FC 27 Ultimate Team: max PlayStyles+ per item drops from five to three.

Direction: attributes first, perks as small modifiers. Use at most 0-2 "Traits" per player, each worth +5-10% on one event.

**Fatigue (official, FC 26).** For AI-controlled players EA applies a reduction in Sprint Speed and Acceleration when fatigued, proportional to fatigue level, with short- and long-term fatigue. Stamina determines how quickly the stamina bar depletes. Copy this model.

**Tactics (official/press).** FC 26 Career "Tactical Visions" renamed Tiki-Taka to Possession and Gegenpressing to High Pressing. FC 27 beta notes: under Team Press, defenders are less effective at applying pressure than midfielders and forwards; lower Defensive Depth makes defenders retreat sooner. Player Lens's `press_intensity` and `def_line` correspond directly.

**Not publicly documented.** EA has never published how its engine turns attributes into pass, shot or tackle success probabilities, or how "sim match" works internally. Anything claiming to be EA's exact formula is speculation.

## 2. EA FC vs Football Manager: which suits a Monte Carlo sim?

FIFA/FC attributes feed an animation and physics engine where a human controls one player, so they can't be lifted directly into dice rolls. Football Manager is a better template:

- FM attributes run 1-20 across Technical, Mental and Physical groups. Sports Interactive's manual says most Physical attributes, plus Anticipation, Decisions and Positioning, are the most heavily rated for any position.
- **Two-step model.** An SI community representative described that for every pass, players use attributes such as vision and decisions to evaluate options, then attributes such as passing, composure and technique to execute it.
- **Recommendation:** use FM's two-step decide/execute model with FIFA's 1-99 scale and grouping. The two steps also make ratings self-explaining, e.g. "chose a high-xT pass (Vision 82), completed it under pressure (Composure 77)."

**Open-source reference.** Google Research Football (Kurach et al., AAAI-20) is an Apache 2.0 11v11 engine whose paper states players have different statistics such as speed or accuracy and get tired over time. It's a physics engine built for reinforcement learning and too heavy for this build, but confirms speed, accuracy and fatigue are the minimum viable core.

## 3. Proposed attribute set (12 outfield + 2 GK, scale 1-99)

| # | Attribute | Why it earns its place |
| --- | --- | --- |
| 1 | Pace (top speed) | EA splits Pace 55/45 into sprint speed and acceleration. Recovery runs and in-behind runs depend on top speed |
| 2 | Acceleration | Pressing and counterpress regains are won in the first 5 m. FC 27 re-weighted toward Acceleration |
| 3 | Passing | Pass execution |
| 4 | Vision | Pass choice: how often the player picks the higher-xT option (FM decide step) |
| 5 | Finishing | Shot execution (on-target %, xG multiplier) |
| 6 | Dribbling | Take-on success and press resistance |
| 7 | Tackling | Tackle and duel success |
| 8 | Anticipation | Interceptions, marking denial, attacking movement |
| 9 | Composure | Accuracy under pressure for passes and shots |
| 10 | Strength/Aerial | Shoulder duels, headers, set pieces |
| 11 | Work rate | Off-ball volume: press triggers, recovery-run propensity, counterpress participation |
| 12 | Stamina | Fatigue depletion rate |
| GK1 | Shot-stopping | Save probability on on-target shots |
| GK2 | Command | Claims crosses, sweeps through balls, distribution accuracy |

Leave out or fold in: weak foot and skill moves (no visible effect on a dots view); Aggression (derive foul propensity from low Tackling, high Work rate and press\_intensity); Heading (fold into Strength/Aerial); long-shot and penalty specialisms (use Finishing plus distance).

Generate archetypes from templates, e.g. "DM ball-winner" gets high Tackling, Anticipation, Work rate and Stamina and mid-range Passing.

## 4. Attribute -> event/movement mapping

Here `z = (attr - 60) / 10`, a standardised skill term that is 0 for an average pro (60). A `+` raises the logit or rate.

| Event / behaviour | Decide step | Execute step | Opposing attributes |
| --- | --- | --- | --- |
| Pass choice | Vision (+ team tempo) | - | - |
| Pass completion | - | Passing (+), Composure (+ under pressure) | Nearest defender's Anticipation |
| Dribble/take-on | Dribbling, Composure | Dribbling, Acceleration, Strength | Tackling, Acceleration |
| Shot decision | Finishing, Composure, distance | - | - |
| Shot outcome | - | xG(dist, angle) x Finishing, Composure | Blocker Anticipation; GK Shot-stopping |
| Header / aerial duel | - | Strength/Aerial | Strength/Aerial |
| Tackle | Work rate (engage) | Tackling, Strength | Dribbling, Strength |
| Interception | Anticipation | Anticipation, Acceleration | Passer's Passing/Vision |
| **Pressure (off-ball credit)** | Work rate x press\_intensity | Acceleration (time to close) | Receiver's Composure, Dribbling |
| **Pressure regain** (ball won within 5 s of pressure) | - | Tackling, Anticipation, Acceleration | Carrier's Composure |
| **Counterpress** (pressure within 5 s of own turnover) | Work rate, Anticipation | Acceleration | - |
| **Recovery run** | Work rate | Pace, Stamina | Attacker's Pace |
| **Marking denial** (target not chosen because marked) | Anticipation | Pace, Strength | Attacker's Anticipation, Acceleration |
| **Decoy run** (run drags a defender, teammate gains space) | Anticipation, Work rate | Acceleration, Pace | Defender's Anticipation |
| Movement speed | - | Pace x fatigue; Acceleration x fatigue | - |
| Fatigue | - | Stamina (decay rate), Work rate (load) | - |
| GK claim / sweep / distribution | Command | Command | Attackers' Strength/Aerial |

Pressure-regain and counterpress definitions follow the Hudl StatsBomb Event Data Glossary: counter pressures are pressures exerted within 5 seconds of a turnover; Counter Pressure Regains are times a player's team won the ball back within 5 seconds of the player counter pressuring an opponent.

## 5. Key formulas and starting parameters (tune these)

**1. Pass success**

- `logit p = 2.6 + 0.25*z_Pass - 0.06*(d - 15) - 1.2*P*(1 - 0.1*z_Comp) - 0.4*F - 0.8*L`
  - d = pass distance (m); P = pressure 0-1, e.g. `max(0, 1 - dist_nearest_defender/5)`; F = 1 if forward into the final third; L = 1 if lofted/long.
- Sanity values: Passing 70, 15 m, unpressured about 94%; same pass under full pressure about 84%; 40 m lofted ball about 60%.
- Published expected-pass work uses the same drivers (distance, pressure, location, direction). Anzer and Bauer, "Expected passes" (Data Mining and Knowledge Discovery, 2022): 840,386 Bundesliga passes; baseline completion 85.2%; extreme gradient boosting reached AUC 93.4%. Logistic regression is the standard interpretable choice.

**2. Shot xG**

- `logit xG = 0.3 - 0.17*dist_m + 1.0*angle_rad` (angle subtended by the goal mouth).
- Multiply odds by `exp(0.15*z_Fin + 0.05*z_Comp)`; by `exp(-0.6*P)` when pressured; by about 0.6 for headers.
- Sanity: central 11 m about 0.28; central 20 m about 0.06.
- Calibration target: mean xG per shot about 0.11-0.12 (2.7-2.9 goals from 23-25 shots).

**3. Save / on-target**

- On-target probability about `0.30 + 0.10*z_Fin` (clamped).
- Goal given on target = `xG_on_target_adjusted * exp(-0.15*z_GK)`.
- Roughly a third of shots on target, about 9 per match from 23-25 shots.

**4. Pass target choice (Vision)**

- Score candidate receivers by `delta_xT * completion_prob`, then softmax with temperature `tau = 1.5 - 0.1*z_Vision`.
- Use Karun Singh's open Expected Threat grid ("Introducing Expected Threat (xT)"), built on 2017/18 Premier League events: a 16x12 grid (192 zones), 4-5 iterations to converge. It is a Markov chain over pitch zones. Example: an Ozil pass moving the ball from xT 0.077 to 0.158 (+0.081).

**5. Fatigue**

- `fatigue += load*dt*(1.5 - 0.01*Stamina)`, load higher for sprints and presses scaled by Work rate.
- `speed = Pace_ms*(1 - 0.15*fatigue)`; `accel = Accel_ms2*(1 - 0.15*fatigue)`.
- Map Pace 1-99 to top speed about 7.0-9.3 m/s, keeping the 9 m/s cap near Pace 90.

**6. Scoreline check (not the engine)**

- Across seeds, goals per team should be roughly Poisson (variance about the mean).
- If 0-0 and 1-1 draws look too rare, that's a known feature of independent Poisson models; Dixon-Coles adds a low-score correction (rho). Compare the sim's score matrix against it rather than forcing it.

## 6. Benchmark stats (Premier League, per match)

| Metric | Target band | Source / note |
| --- | --- | --- |
| Passes (both teams) | 850-940 | Opta via premierleague.com: 941.0 (2023/24), 893.5 (2024/25), 849.1 (first 50 games of 2025/26); statz.ai: 885.6 after 70 games of 2026/27 |
| Pass completion | 82-84% | Opta via premierleague.com: 82.9% (2023/24), 83.7% (2024/25), 82.6% (2025/26) |
| Shots (both teams) | 22-25 | Opta Analyst: 22.5 early 2025/26, lowest rate of attempts in any PL season on record; 2024/25 had 8.3/game from outside the box (31.7%) |
| Shots on target (both) | about 9 | FotMob/Opta team figures 2024/25; average across 20 teams about 4.55/team |
| Goals | 2.5-3.0 | 2.93 (2024/25), 3.28 record (2023/24), 2.48 early 2025/26 |
| xG per shot | about 0.11-0.12 | Implied by goals / shots |
| Tackles won / interceptions (per team) | about 10 / about 8 | FBref Big-5 snippet 2025/26, unconfirmed (may be tackles won only) |
| Pressures (per team) | 115-175 (most 125-150) | FBref/StatsBomb 2020/21 via Brindescu et al. (2021) |
| Possessions facing immediate pressure | about 47% of open-play | StatsBomb pressure-data analysis (secondary write-up) |
| Distance per team | 110-118 km | 2026/27 team averages (GiveMeSport, citing tracking data) |
| Distance per outfield player | 10-12 km (GKs about 5 km) | Multiple tracking-based summaries |
| Sprints (>25 km/h) | about 140 per team; 10-15 per outfield player | Sky Sports (2023/24 record); Opta sprint definition |
| Fouls (per team) | about 10-12 | StatMuse 2025/26 |
| Cards (total) | about 4 | FootyStats: 4.08 per game |
| Corners (both) | about 9.5-10.5 | FootyStats (aggregator, low confidence) |
| Offsides (per team) | about 1.5-2 | Unsourced rule of thumb; verify before claiming |

Derived checks for a 1 Hz engine:

- 10.8 km over 5,400 s is an average of only about 2 m/s. If dots spend much time near 9 m/s, distance will blow past 12 km. Use jog and walk states.
- About 900 passes per match is roughly one pass every 6 s of total clock, or every 3-4 s of ball-in-play.

## 7. Calibration checklist (about half a day)

1. **Instrument first.** Log every event with player ID, attributes used, probability and outcome, so rating explanations and calibration share one data source.
2. **Batch run.** 200-500 seeds headless; print mean +/- SD for each benchmark row.
3. **Tune in order**, one knob per metric: tempo / decision interval -> pass volume; pass intercept (2.6) -> completion %; shot-decision propensity -> shots; xG intercept (0.3) -> goals; press trigger rate -> pressures; foul term -> fouls.
4. **Check spreads, not just means.** Goals per team roughly Poisson. Possession should vary with style: Azure's high press should produce more pressures, more attacking-third regains, and higher distance and sprint counts than Redmond's deeper block.
5. **Check attribute sensitivity.** Swap a 50 and an 85 Finisher: conversion should move noticeably but stay plausible, roughly 0.08 -> 0.15 goals per shot. If one attribute dominates, shrink its coefficient.
6. **Fix the demo seed.** After calibration, pick a seed whose match totals sit near the means and use it for the judged demo.

## 8. Licensing / IP

- **Mechanics are fine to borrow.** US Copyright Office circular FL-108: copyright does not protect the idea for a game, its name or title, or the method of playing it. A face-stat-plus-sub-attribute structure, 1-99 ratings, roles and fatigue-reduces-speed are safe.
- **Don't copy EA's specific expression:** no rating data, no real player ratings, no card art, no EA-branded feature names. Say "Traits", not "PlayStyles"; "Style" or "Game Plan", not "Tactical Visions". Don't imply EA endorsement.
- **Keep names fictional.**
- **Open data for calibration:** StatsBomb open data requires attribution. Opta and FBref figures are facts but cite them and don't redistribute datasets.
- General information, not legal advice. Because the event is Premier League-partnered, check the hackathon rules on PL marks.

## Caveats

- EA formulas are unpublished. Face-stat weightings and OVR/IR tables come from a 2015-2019 community analysis (fifauteam.com) and may have changed.
- FM internals are also opaque; the decide-then-execute description comes from an SI community representative, not technical documentation.
- Some benchmark figures are secondary: FBref tackles/interceptions, FootyStats corners and cards, the 47% immediate-pressure figure. Pressures data is from 2020/21. Offsides is unsourced.
- Benchmarks are moving: PL passing and shot volumes have dropped since 2023/24. Calibrate to bands, not single numbers.
- The coefficients are starting values chosen to hit sensible sanity points, not fitted to data. The calibration loop is what makes them accurate.

## Sources

- EA: [FC 25 FC IQ deep dive](https://www.ea.com/en/games/ea-sports-fc/fc-25/news/pitch-notes-fc-25-fc-iq-deep-dive), [FC 25 FUT deep dive](https://www.ea.com/en/games/ea-sports-fc/fc-25/news/pitch-notes-fc-25-football-ultimate-team-deep-dive), [FC 26 gameplay deep dive](https://www.ea.com/en/games/ea-sports-fc/fc-26/news/pitch-notes-fc26-gameplay-deep-dive), [FC 27 gameplay deep dive](https://www.ea.com/games/ea-sports-fc/fc-27/news/pitch-notes-fc27-gameplay-deep-dive), [FC 27 launch update](https://www.ea.com/games/ea-sports-fc/fc-27/news/pitch-notes-fc27-launch-update)
- Attributes and ratings (community): [fifauteam FIFA 16 attributes](https://fifauteam.com/fifa-16-attributes/), [fifauteam FIFA 19 ratings guide](https://fifauteam.com/player-ratings-guide-fifa-19/), [fifauteam FC 26 roles](https://fifauteam.com/fc-26-roles/), [fcratings FC 26 attributes](https://www.fcratings.com/articles/ea-sports-fc-26-attributes-explained)
- Football Manager: [SI manual FM2022 players](https://community.sports-interactive.com/sigames-manual/football-manager-2022/players-r4507/), [fmdossier attributes](https://fmdossier.dev/guides/player-attributes-explained)
- Premier League benchmarks: [Opta Analyst long balls/trends 2025/26](https://www.premierleague.com/en/news/4426039/opta-analyst-on-long-balls-long-throws-key-tactical-trends-spotted-in-2025-26-season), [statz.ai passing](https://statz.ai/competitions/premier-league/stats?group=passing), [Opta Analyst 2024/25 shot data](https://theanalyst.com/articles/premier-league-2024-25-shot-data), [Opta Analyst goals](https://theanalyst.com/articles/premier-league-goals-low-stats), [Opta Analyst MD1 stats](https://theanalyst.com/articles/premier-league-md1-stats-off-the-charts), [Sky Sports trends](https://www.skysports.com/football/news/13122695/premier-league-trends-title-race-goals-speed-sprints-pressing-high-lines-formations-and-much-more), [GiveMeSport distance](https://www.givemesport.com/premier-league-teams-ranked-distance-run-this-season/), [StatMuse fouls](https://www.statmuse.com/fc/ask/premier-league-teams-fouls-per-game), [FootyStats cards](https://footystats.org/england/premier-league/card-stats), [FootyStats corners](https://footystats.org/stats/average-corners)
- Models: [Dixon-Coles overview](https://metricgate.com/docs/dixon-coles-soccer-model/), [StatsBomb counter-pressing](https://readmedium.com/harnessing-statsbomb-data-to-evaluate-counter-pressing-ebc3ff06e818)
- IP: [Tetris Holding v. Xio Interactive](https://en.wikipedia.org/wiki/Tetris_Holding,_LLC_v._Xio_Interactive,_Inc.)
