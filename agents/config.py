"""Knobs for the commentary pipeline. Every number here is a guess or a spec value; change it in one place.

Cadence values come from ARCHITECTURE, "Commentary cadence". Prices come from env vars (app/settings.py),
never from here.
"""

CHUNK_S = 60  # a chunk is one match minute of one player
MAX_CHUNK = 89  # chunk index = min(floor(t / 60), 89); the last chunk is closed at 5400 s

LINE_MIN_GAP_S = 5  # at least this long between the end of one line and the start of the next
LINE_MAX_SILENCE_S = 25  # after this long with no line, a quiet-spell line fills in (owner, Oct 27; was 15, then 120, then 50)
REACTION_DELAY_S = 8  # a short reaction line this long after a goal
BIG_IMPORTANCE = 0.8  # at or above: may interrupt the minimum gap, renders large, excited tone
# Every visible rating-log row (any non-zero change, positive or negative, however small) gets a line (owner, Oct 27):
# it is what the rating is made of. A row that lands too soon after another line waits up to RATING_MAX_DELAY_S;
# if it still can't fit, it joins the previous rating line so it is never dropped.
RATING_LINE_IMPORTANCE = 0.4  # at least this, so a rating line wins a slot over play and stat lines
RATING_MAX_DELAY_S = 10  # guess: later than this, the line would no longer match what is on the pitch
REACTION_IMPORTANCE = 0.6
FILLER_IMPORTANCE = 0.1
LINE_EST_S = 3.5  # guess: a line takes about this long to speak (HD voice clips measured 3.5 to 5 s)
FILLER_AFTER_S = 20  # a quiet-spell line goes this long after the previous line ends
# A quiet-spell line is about the game around the ball ("play", from the events at that second), except that a stat line
# about the selected player ("filler": distance, rating, activity) comes at most every STAT_EVERY_S (owner: repetitive).
STAT_EVERY_S = 180
PLAY_IMPORTANCE = 0.15
PLAY_NEAR_M = 25.0  # a play line prefers an event whose player is within this distance of the selected player (keeps him in frame)
ACTIVITY_REPEAT_S = 120  # a play line mentions what the player is doing only if it changed and was not said this recently
STAT_TOPICS = ("distance", "rating", "activity")  # a stat line talks about one topic, rotating; activity only when it changed
PLAY_WINDOW_S = (8.0, 2.0)  # the play line describes the latest on-ball event from 8 s before to 2 s after its second
# Event types a play line can describe, and the Fact Guard action category each one allows.
PLAY_ACTIONS = {
    "pass": "pass", "key_pass": "pass", "dribble": "dribble", "tackle": "tackle", "interception": "interception",
    "aerial_duel": "header", "clearance": "clearance", "block": "block", "shot": "shot", "save": "save",
    "pressure": "press", "pressure_regain": "press", "counterpress": "press", "foul": "foul", "offside": "offside",
    "throw_in": "restart", "goal_kick": "restart", "corner": "restart", "free_kick": "restart", "kickoff": "restart",
}

MIN_WORDS = 6
MAX_WORDS = 14

SPELL_WINDOW_S = 300  # rating/spells.py windows
PREVIOUS_LINES = 3  # the Commentator sees the player's last few final lines to avoid repeating itself

# Rating log reason codes that count as a "key event" for the player (shot, key pass, tackle, foul, card).
KEY_EVENT_KINDS = {"goal", "shot", "key_pass", "tackle", "foul", "card"}

# Rating log reason code -> fact kind (anything not listed becomes a plain rating_change fact).
REASON_KIND = {
    "goal": "goal", "assist": "key_pass", "key_pass": "key_pass",
    "shot_on_target": "shot", "big_chance_missed": "shot",
    "tackle": "tackle", "interception": "tackle", "block": "tackle", "clearance": "tackle", "aerial_duel_won": "tackle",
    "foul_won": "foul", "foul_committed": "foul", "handball": "foul", "offside": "foul",
    "card_yellow": "card", "card_red": "card",
    "counterpress": "counterpress", "pressure_regain": "pressure_regain", "recovery_run": "recovery_run",
    "marking_denial": "marking_denial", "decoy_run": "decoy_run",
}
# Values in a rating entry that hold player ids; they are turned into display names for the facts.
NAME_KEYS = ("opponent", "passer", "shooter", "scorer", "receiver", "teammate")

# Calls (specs/agents-backend.md: 20 s per LLM call, 10 s per Speech call; a failed call retries once)
LLM_TIMEOUT_S = 20
SPEECH_TIMEOUT_S = 10
LLM_MAX_CONCURRENT = 6  # parallel LLM calls (the deployment allows 250k tokens/min; a chunk uses about 20k)
LLM_MAX_OUTPUT_TOKENS = 1500
SPEECH_BITRATE = 48_000  # audio-24khz-48kbitrate-mono-mp3: clip seconds = bytes * 8 / this

AGENT_NAMES = ("interpreter", "moments", "commentator", "fact_guard", "personalizer", "voice_director", "recap")
# Temperatures from the spec: 0.2 for Interpreter, Moments and Voice Director; 0.7 for Commentator and Personalizer.
TEMPERATURE = {"interpreter": 0.2, "moments": 0.2, "commentator": 0.7, "fact_guard": 0.2, "personalizer": 0.7, "voice_director": 0.2, "recap": 0.5}

# Speech delivery (guesses, tune by ear). HD voices took rate and pitch changes in the voice tests.
# Emotion for the voice. Microsoft's HD voices take a style name (docs: "Expressive style tags"); <prosody> (rate, pitch, volume) is NOT
# supported on them, so the Voice Director's job is to pick a style per line. "default" means no tag (the voice's own reading).
HOME_TEAM = "azc"  # owner: both commentators are Azure City's home commentators, in every language
VOICE_STYLES = (  # the 14 football emotions the owner approved by ear (Oct 27), plus "default" (no tag)
    "ecstatic", "excited", "happy", "proud", "shocked", "amazed", "frustrated", "angry", "disappointed", "defeated", "anxious",
    "urgent", "confident", "determined", "shouting", "default",
)
# Which emotions fit a moment, by what it means for Azure City ("side", computed by code in agents/inputs.home_side).
# Owner (Oct 27): "this is a football match, not golf": hyped on every line, so calm and confident are not used.
STYLES_FOR = {
    "good": ("excited", "ecstatic", "amazed", "shocked", "shouting", "urgent", "proud", "happy"),
    "bad": ("frustrated", "angry", "disappointed", "defeated", "anxious", "urgent", "shocked"),
    "neutral": ("excited", "urgent", "anxious", "determined"),
}
BIG_STYLES = {  # importance >= BIG_IMPORTANCE (goals, cards involving the player): never flat
    "good": ("ecstatic", "shouting", "excited", "amazed", "shocked"),
    "bad": ("defeated", "disappointed", "shocked", "frustrated", "angry"),
    "neutral": ("excited", "shocked", "amazed", "urgent"),
}
# Stat (filler) lines are most of the match: milder emotions, by the score (owner: "frustrated" over a jog sounded wrong).
STAT_STYLES = {
    "good": ("excited", "happy", "proud", "urgent", "determined"),
    "bad": ("urgent", "anxious", "determined"),
    "neutral": ("excited", "urgent", "determined"),
}
STAT_DEFAULT = {"good": "excited", "bad": "urgent", "neutral": "excited"}
# The last minutes: every non-stat moment is read with more intensity (owner: Lima's 89' header should sound excited).
LATE_MINUTE = 85  # from this match minute on (88' is t >= 5220 s); guess, tune by ear
LATE_STYLES = {
    "good": ("excited", "ecstatic", "shouting", "amazed", "shocked", "urgent"),
    "bad": ("anxious", "urgent", "defeated", "frustrated", "shocked", "angry"),
    "neutral": ("urgent", "anxious", "excited"),
}
# Mood: the commentator's emotion carries from line to line and fades (owner: not after one line, not forever). Every
# earlier non-stat moment adds its sign for Azure City times a weight, decaying as exp(-age / MOOD_TAU_S): a goal alone
# keeps the mood hot for about a minute and warm for about two and a half; a run of good moments keeps it up. Guesses.
MOOD_TAU_S = 75
MOOD_GOAL_WEIGHT = 1.5  # a goal; other big moments weigh 1.0, the rest their importance
MOOD_HOT = 0.6  # at or above: stat lines keep full intensity in that direction
MOOD_WARM = 0.25  # at or above: stat lines lean that direction instead of following the score
MAX_SAME_STYLE_RUN = 2  # code changes the third line in a row with the same emotion
SIDE_DEFAULT = {"good": "excited", "bad": "frustrated", "neutral": "excited"}  # owner: exaggerate, never flat  # when the model's pick does not fit
BIG_DEFAULT = {"good": "ecstatic", "bad": "defeated", "neutral": "excited"}
LATE_DEFAULT = {"good": "excited", "bad": "anxious", "neutral": "urgent"}
BIG_TRIGGERS = ("goal", "card", "penalty")  # always read with a big emotion, whatever their importance
# Danger: the ball within this many metres of a goal line at the moment's second (the crowd swells over the same zone:
# web/src/lib/crowd.ts ramps from 70 to 95 m and from 35 to 10 m). Azure City attack left to right all match.
DANGER_X_HOME_ATTACK = 80.0  # x >= this: Azure City near Redmond's goal
DANGER_X_AWAY_ATTACK = 25.0  # x <= this: Redmond near Azure City's goal
# Omni voice parameters (docs: higher temperature and top_p = more expressive, higher cfg_scale = faster, closer to the text).
# Defaults are 0.7 / 0.7 / 1.4; pushed up for a hyped commentator (guess, tune by ear).
VOICE_PARAMS = "temperature=0.9;top_p=0.9;cfg_scale=1.6"
STYLE_SYNTAX = "express-as"  # or "bracket" ("[excited] text"); both are documented, the owner picks by ear (guess)
STYLE_LANGS = ("en", "es")  # languages that get a style tag; Microsoft documents styles for English only, Spanish is by ear
PAUSE_MS = 250  # length of a pause the Voice Director marked, when SSML_PAUSES is on
SSML_PAUSES = False  # owner: pauses made the voice stumble mid-phrase ("11.0 ... kilometres"), so they are off
SSML_EMPHASIS = False  # <emphasis> is not supported on HD voices
SPEECH_LOCALE = {"en": "en-GB", "es": "es-MX"}

# Full-time recap (specs/agents-backend.md open question: "about 60 to 90 words")
RECAP_WORDS = (40, 90)
