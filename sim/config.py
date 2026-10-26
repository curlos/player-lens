"""Every simulator tuning knob in one place (specs/simulator-movement.md and specs/simulator-possession.md).

All numbers are starting guesses calibrated against the benchmark bands in ARCHITECTURE section 3
(see docs/validation-report.md). None of them are researched facts unless a comment says so.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Pitch (Laws of the Game; meters, origin top-left, x along the length)
# ---------------------------------------------------------------------------
PITCH_L = 105.0
PITCH_W = 68.0
GOAL_HALF_WIDTH = 3.66
BOX_DEPTH = 16.5
BOX_HALF_WIDTH = 20.16
GOAL_AREA_DEPTH = 5.5
PENALTY_SPOT = 11.0
CENTER_CIRCLE_R = 9.15
DURATION_S = 5400

# ---------------------------------------------------------------------------
# Formations: normalized (x from own goal line toward the opponent, y across), keyed by shirt number.
# Written for a team attacking left to right; the away side is mirrored (x -> 1 - x, y -> 1 - y).
# ---------------------------------------------------------------------------
FORMATION_XY: dict[str, dict[int, tuple[float, float]]] = {
    "4-3-3": {
        1: (0.04, 0.50), 2: (0.25, 0.86), 3: (0.25, 0.14), 4: (0.21, 0.62), 5: (0.21, 0.38),
        6: (0.35, 0.50), 8: (0.45, 0.68), 10: (0.47, 0.32), 7: (0.60, 0.86), 9: (0.64, 0.50), 11: (0.60, 0.14),
    },
    "4-4-2": {
        1: (0.04, 0.50), 2: (0.23, 0.86), 3: (0.23, 0.14), 4: (0.20, 0.62), 5: (0.20, 0.38),
        6: (0.38, 0.60), 8: (0.38, 0.40), 7: (0.42, 0.87), 11: (0.42, 0.13), 9: (0.58, 0.58), 10: (0.58, 0.42),
    },
}

# Team style, 0-1 floats plus style (guesses): Azure presses high with a high line; Redmond sits deeper.
TEAM_TACTICS: dict[str, dict[str, float | str]] = {
    "azc": {"press_intensity": 0.80, "tempo": 0.65, "width": 0.70, "def_line": 0.70, "style": "balanced"},
    "rdm": {"press_intensity": 0.50, "tempo": 0.50, "width": 0.50, "def_line": 0.45, "style": "direct"},
}

# ---------------------------------------------------------------------------
# Movement
# ---------------------------------------------------------------------------
SPEED_CAP = 9.0  # m/s, hard cap for anyone
BASE_SPEED, PACE_SPEED = 7.0, 2.0  # max_speed = min(9, 7 + 2 * pace / 99)
BASE_ACCEL, PACE_ACCEL = 2.5, 2.0  # accel = 2.5 + 2 * pace / 99
FATIGUE_SPEED_LOSS = 0.25  # max_speed and accel scale by (1 - 0.25 * fatigue)
ARRIVAL_RADIUS = 0.5
PITCH_MARGIN = 0.5  # targets are kept this far inside the lines

# Intent speed caps (m/s) shape the desired speed only; move_player still applies its own limits.
INTENT_SPEED = {
    "hold_shape": 2.6, "mark": 3.8, "press": 8.0, "track_back": 8.5, "make_run": 7.5, "carry": 6.2,
    "support": 3.0, "reset": 2.2, "celebrate": 6.5, "huddle": 5.0, "talk_ref": 3.0, "down": 0.0,
    "wall": 3.0, "set_piece_wait": 3.0, "take_set_piece": 3.0, "sent_off": 2.0, "keeper": 4.0,
}
TEAM_WORK_SPEED = (0.90, 0.15)  # off-ball speed factor = a + b * press_intensity
SLOW_NEAR_TARGET_M = 4.0  # within this distance of a hold_shape target players only walk
WALK_SPEED = 1.6
CATCH_UP_SPEED = 4.6  # hold_shape when more than 15 m from the shape target

# Team shape (meters in the team's own frame).
PUSH_UP_BASE, PUSH_UP_LINE = 9.0, 9.0  # in possession: shape moves up by base + line * def_line
DROP_BASE, DROP_LINE = 3.0, 6.0  # out of possession: shape drops by base + line * (1 - def_line)
BALL_SHIFT_X, BALL_SHIFT_Y = 0.30, 0.25
WIDTH_IN_POSSESSION = (0.95, 0.20)  # y spread = a + b * width
WIDTH_OUT_OF_POSSESSION = (0.72, 0.15)

# Pressing and marking.
PRESS_TRIGGER_BASE, PRESS_TRIGGER_K = 8.0, 16.0  # trigger distance = base + k * press_intensity
SECOND_PRESSER_MIN_INTENSITY = 0.6
SECOND_PRESSER_RANGE = 0.6  # fraction of the trigger distance
PRESS_MAX_S = {"high": 9, "low": 5}  # keep pressing this long, then drop off
PRESS_COOLDOWN_S = 4
PRESS_MAX_FROM_SHAPE = 28.0  # a presser never chases this far from their shape target
DANGER_ZONE_M = 32.0  # within this of our goal line the nearest two always press
DANGER_PRESS_M = 20.0
MARK_ZONE_M = 11.0
MARK_OFFSET_M = 1.75
RECOVERY_DISTANCE_M = 15.0  # track back when this far from the shape target and beyond the ball

# Attacking runs.
RUN_START_P = 0.05  # per second, scaled by 0.5 + work_rate / 99
RUN_LENGTH_S = (3, 6)
RUN_FORWARD_M = (8.0, 15.0)
RUN_RESPECTS_OFFSIDE_P = 0.97
OFFSIDE_LINE_MARGIN = 2.5

# Goalkeeper.
GK_MAX_OFF_LINE = 12.0
GK_Y_FOLLOW = 0.25

# Referee.
REF_SPEED, REF_ACCEL = 5.0, 2.5
REF_OFFSET_M = 12.0

# Fatigue: fatigue += k * (speed / max_speed)^2 * load, load from Work rate and Stamina.
FATIGUE_K = 0.0016
FATIGUE_RECOVERY = 0.00035  # per second while walking or standing
FATIGUE_MAX = 1.0

# Activity speed thresholds (m/s).
ACT_STAND, ACT_WALK, ACT_JOG, ACT_RUN = 0.5, 2.0, 4.0, 7.0

# ---------------------------------------------------------------------------
# Possession and decisions
# ---------------------------------------------------------------------------
DECISION_INTERVAL = (4, 6)  # seconds between decisions, shortened by tempo and pressure
PRESSURED_DECISION_M = 1.5
PASS_RANGE = (4.0, 45.0)
PASS_CANDIDATES_BASE = 4  # plus vision // 25
PASS_SPEED, LOFTED_SPEED = 15.0, 18.0
LOFTED_DISTANCE = 30.0

# Option scores (softmax inputs).
W_FORWARD = {"direct": 0.70, "balanced": 0.50, "patient": 0.35}  # per 10 m gained
W_OPEN = {"direct": 0.6, "balanced": 0.8, "patient": 1.0}
W_SAFE = 3.4  # times completion probability
W_THREAT = 2.0  # times the receiver's threat gain (x10)
CARRY_BASE = 0.6
DRIBBLE_BASE = 0.2
SHOT_WEIGHT = 15.0
SHOT_BIAS = -0.75
BIG_CHANCE_BOOST = 1.2
SHOT_MIN_XG = 0.025
SHOT_RANGE = 30.0
CLEAR_WEIGHT = 2.5
SOFTMAX_TEMP = 0.55  # falls with Composure
SOFTMAX_TEMP_COMPOSURE = 0.05

# Pass completion (research doc formula 1): logit = base + 0.25 z_pass - 0.06 (d - 15) - 1.2 P (1 - 0.1 z_comp) - 0.4 F - 0.8 L
PASS_BASE = 3.3
PASS_Z = 0.18
PASS_DIST = 0.06
PASS_PRESSURE = 1.2
PASS_FINAL_THIRD = 0.4
PASS_LOFTED = 0.8
PASS_LANE = 0.75  # per meter a defender is inside 2.5 m of the lane
PASS_INTO_BOX = 1.2  # a crowded box: passes into it from outside are harder
PASS_MARKED = 0.6  # per meter the receiver's marker is inside RECEIVER_MARKED_M
RECEIVER_MARKED_M = 3.0
PASS_INTERCEPT_SHARE = 0.65
MISPLACED_ERROR = (5.0, 0.25)  # meters: base + k * distance  # failed passes with a defender near the lane are intercepted this often

# Shots and xG (research doc formula 2): logit xG = a - 0.17 d + 1.0 angle.
XG_INTERCEPT = -0.85
XG_DIST = 0.17
XG_ANGLE = 1.0
XG_PRESSURE = 0.6
XG_HEADER = 0.6
HEADER_SHOT_BASE, HEADER_SHOT_XG, HEADER_SHOT_MAX = 0.2, 4.0, 0.7  # chance a won header becomes a shot
CROSS_COMPLETION = 0.55  # crosses find a teammate far less often than ground passes
XG_FREE_KICK = 0.55
PENALTY_XG = 0.76
BLOCK_LINE_M = 1.6
BLOCK_P_EACH = 0.45
ON_TARGET_BASE = 0.24
ON_TARGET_FIN = 0.06
ON_TARGET_XG = 0.9
GOAL_K = 0.95  # P(goal) = GOAL_K * xG * skill multiplier, before blocks
FIN_ODDS, COMP_ODDS, GK_ODDS = 0.15, 0.05, 0.15
POST_SHARE = 0.12  # of off-target shots with xG above 0.05
SAVE_HOLD, SAVE_CORNER = 0.55, 0.30  # remainder is a loose rebound
SHOT_SPEED_KMH = (78.0, 8.0, 108.0)  # mean, sd, cap (ball speed cap is 30 m/s = 108 km/h)
HEADER_SPEED_KMH = (55.0, 8.0)

# Duels, tackles and fouls.
TACKLE_RADIUS = 2.0
TACKLE_ATTEMPT_P = (0.05, 0.08)  # base + k * press_intensity, per second
TACKLE_UNPRESSED = 0.5  # a nearby defender who is not pressing tries less often
BLOCKER_M = 5.0  # a goal-side defender this close stops the carrier running straight at goal
BLOCKER_DUEL_P = 0.12  # per second near our goal: the blocker forces a duel
DUEL_BASE = 0.15  # logit that the carrier keeps the ball
DUEL_SKILL = 0.22
DUEL_PACE = 0.10
TACKLE_KEEPS_BALL = 0.65
BEATEN_COOLDOWN_S = 3
FOUL_P = 0.19  # per duel
FOUL_IN_OWN_BOX = 0.035  # defenders are careful in their own box
FOUL_TEMPERAMENT = {"calm": 0.7, "normal": 1.0, "hot-headed": 1.5}
FOUL_PRESS = 0.4  # multiplier 1 + k * (press_intensity - 0.5)
FOUL_ON_YELLOW = 0.4  # not for hot-headed players
YELLOW_P = 0.11
YELLOW_HOT = 0.08
RED_P = 0.004
DOGSO_RANGE = 25.0  # denying a clear goal chance: last defender, this close to goal
DOGSO_P = 0.05  # share of such fouls the referee judges a clear chance
DISSENT_P = 0.06  # hot-headed offender booked for dissent after a foul
REF_ERROR_P = 0.03
INJURY_P = 0.035
PRESSURE_RADIUS = 1.1
PRESSURE_MIN_SPEED = 3.0  # a pressure is a presser closing in, not one standing next to the carrier
PRESSURE_REPEAT_S = 30  # the same presser on the same carrier counts again only after this

# Aerial and goalkeeper.
AERIAL_CONTEST_M = 2.5
AERIAL_STRENGTH = 0.06  # logit per Strength point difference
GK_CLAIM_P = 0.55
GK_SWEEP_P = 0.7
HANDBALL_P = 0.02  # of blocks

# Offside: the referee misses or wrongly calls this share.
OFFSIDE_ERROR_P = 0.03

# Restarts: seconds of dead time (low, high).
RESTART_WAIT = {
    "throw_in": (5, 8), "goal_kick": (8, 12), "corner": (15, 20), "free_kick": (8, 14),
    "penalty": (28, 35), "kickoff": (36, 44), "offside": (6, 10),
}
CELEBRATION_S = 7
# Sent-off players walk to the bottom touchline, away from the score bar at the top center; the frontend
# fades the dot out once they get there. Azure goes to the left of halfway, Redmond to the right.
SENT_OFF_Y = PITCH_W
SENT_OFF_X_OFFSET = 7.5
CARD_EXTRA_WAIT = (8, 14)
INJURY_DOWN_S = (5, 10)
DEAD_BALL_SPEED = 12.0  # m/s while the ball is fetched to the restart spot
FK_DIRECT_RANGE = 30.0
FK_DIRECT_P = 0.25
