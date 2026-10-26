"""Rating knobs in one place (specs/rating-model.md). Starting values to tune against simulator output.

Values not in the spec table are marked "guess".
"""

START = 6.0
MIN_RATING, MAX_RATING = 3.1, 9.9  # display range; never 3.0 or 10.0
SOFT_CAP_TOP, SOFT_CAP_BOTTOM, SOFT_CAP_SPAN = 10.0, 3.0, 3.0  # gains x min(1, (10 - r) / 3), losses x min(1, (r - 3) / 3)

# reason_code -> raw delta before repeat decay (spec table).
DELTAS: dict[str, float] = {
    "goal": 1.0,
    "assist": 0.6,
    "key_pass": 0.2,
    "shot_on_target": 0.15,
    "big_chance_missed": -0.3,
    "tackle": 0.15,
    "interception": 0.12,
    "block": 0.2,
    "clearance": 0.08,
    "aerial_duel_won": 0.08,
    "dribble": 0.1,
    "beaten_by_dribble": -0.04,
    "foul_won": 0.05,
    "pressure_regain": 0.12,
    "counterpress": 0.15,
    "recovery_run": 0.15,
    "marking_denial": 0.05,
    "decoy_run": 0.1,
    "dispossessed": -0.08,
    "foul_committed": -0.1,
    "handball": -0.15,
    "offside": -0.05,
    "card_yellow": -0.3,
    "card_red": -1.5,
    "error_leading_to_goal": -1.0,
    "error_leading_to_goal_earlier": -0.3,
    "gk_claim": 0.1,
    "gk_sweep": 0.12,
}
GK_SAVE_BASE, GK_SAVE_XG, GK_SAVE_CAP = 0.1, 0.8, 0.6  # save = +0.1 + 0.8 xG, capped at +0.6
GK_CONCEDED_BASE, GK_CONCEDED_XG = 0.2, 0.7  # conceded = -(0.2 + 0.7 (1 - xG))
MARKING_DENIAL_CAP = 0.3  # total per player per match

# Repeat decay (guess): the n-th earlier occurrence of the same credit scales it by max(FLOOR, BASE^n).
REPEAT_DECAY_BASE, REPEAT_DECAY_FLOOR = 0.85, 0.25
NO_DECAY = {"goal", "assist", "gk_save", "gk_goal_conceded", "marking_denial", "error_leading_to_goal",
            "error_leading_to_goal_earlier", "card_yellow", "card_red"}

OFF_BALL = {"pressure_regain", "counterpress", "recovery_run", "marking_denial", "decoy_run",
            "shape_kept", "shape_out_of_position", "shape_walking", "shape_no_change"}

# Shape checks (guess): every 30-45 s without another entry, compare position to the shape target.
SHAPE_INTERVAL_MIN, SHAPE_INTERVAL_SPAN = 30, 16  # interval = 30 + (deterministic offset % 16) seconds
SHAPE_KEPT_DEV_M = 3.0  # mean distance from the shape target at or below this is credited
SHAPE_KEPT_MIN_WORK = 0.45  # ... if the player was jogging or faster at least this share of the window
SHAPE_OUT_DEV_M = 14.0  # mean distance above this is penalized
SHAPE_WALK_DEV_M = 9.0  # walking while this far out of position when the team is defending
SHAPE_WALK_SHARE = 0.4
SHAPE_DELTAS = {"shape_kept": 0.02, "shape_out_of_position": -0.03, "shape_walking": -0.05, "shape_no_change": 0.0}

# Off-ball detection (guesses unless the spec fixes them).
COUNTERPRESS_WINDOW_S = 5  # spec: pressure within 5 s of our own turnover
REGAIN_WINDOW_S = 5  # spec: ball won back within 5 s of the pressure
REGAIN_NEAR_M = 10.0  # guess: the presser must still be this close to the ball when it is won back
RECOVERY_WINDOW_S = 8
RECOVERY_MIN_TRACK_S = 3
RECOVERY_MIN_RUN_M = 12.0
RECOVERY_AHEAD_M = 5.0
MARKING_WINDOW_S = 300
MARKING_TIGHT_M = 2.5
MARKING_MIN_SHARE = 0.5
MARKING_MIN_SECONDS = 40
DECOY_MIN_RUN_S = 3
DECOY_DRAG_M = 5.0
DECOY_DEFENDER_MOVE_M = 6.0
DECOY_FREE_RECEIVER_M = 4.0
DECOY_COOLDOWN_S = 60
BIG_CHANCE_XG = 0.25
ERROR_WINDOW_S = 10
ERROR_ZONE_M = 35.0  # a turnover this close to our own goal line counts as "a dangerous spot"

# Event importance (0-1): base weight by type, times context, nudged by the rating change (guesses
# except the anchors in the spec: goal 1.0, red 0.9, big save 0.7, key pass 0.3, routine pass 0.05).
IMPORTANCE_BASE: dict[str, float] = {
    "goal": 1.0, "card_red": 0.9, "penalty": 0.85, "error_leading_to_goal": 0.75, "big_chance_missed": 0.6,
    "card_yellow": 0.45, "key_pass": 0.3, "handball": 0.3, "injury": 0.3, "block": 0.25, "corner": 0.2,
    "pressure_regain": 0.18, "tackle": 0.15, "dribble": 0.15, "foul": 0.15, "recovery_run": 0.15,
    "gk_sweep": 0.15, "interception": 0.12, "counterpress": 0.12, "decoy_run": 0.12, "gk_claim": 0.12,
    "free_kick": 0.12, "clearance": 0.1, "offside": 0.1, "aerial_duel": 0.08, "marking_denial": 0.08,
    "pressure": 0.06, "pass": 0.05, "kickoff": 0.05, "throw_in": 0.03, "goal_kick": 0.03, "shape_check": 0.02,
}
IMPORTANCE_LATE_T, IMPORTANCE_LATE = 4500, 1.15
IMPORTANCE_CLOSE = 1.1  # score within one goal before the event
IMPORTANCE_TITLE = 1.1
IMPORTANCE_DELTA_K, IMPORTANCE_DELTA_CAP = 0.25, 0.2

# Spells (guesses): 5-minute windows labelled from events only (rating/spells.py). Commentary context, never rated.
SPELL_WINDOW_S = 300
SPELL_CONTROL_SHARE = 0.62  # share of the window's passes
SPELL_CONTROL_MIN_ENTRIES = 4  # completed passes into the final third
SPELL_CONTROL_RATIO = 2.0  # ... at least this many times the other team's
SPELL_PRESS_MIN = 4  # pressures in the opponent half (a window usually has 0 to 4)
SPELL_PRESS_RATIO = 2.0
SPELL_CHAOS_TURNOVERS = 7  # tackles plus interceptions (a window usually has 3 to 10)
SPELL_CHAOS_SHOTS = 2  # shots by both teams together
