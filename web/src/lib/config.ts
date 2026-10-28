/**
 * Frontend knobs in one place. Values marked "guess" are presentation choices, tune freely;
 * everything else comes from specs/frontend.md.
 */

/** The only playback rates (owner decision Oct 26). */
export const SPEEDS = [1, 2, 4, 10, 30] as const;
export type Speed = (typeof SPEEDS)[number];

/** Highlight chips and timeline clicks seek this many seconds before the event. */
export const HIGHLIGHT_LEAD_S = 8;
/** A rating log row seeks this many seconds before its change, to show the action that caused it (guess; owner, Oct 27). */
export const RATING_LOG_LEAD_S = 4;
/** Arrow keys seek by this many seconds. */
export const ARROW_SEEK_S = 5;
/** The control bar hides this long after the mouse stops over the pitch, then fades for 0.3 s (owner: 2 s or less in all, like a video player). */
export const CONTROLS_HIDE_MS = 1500;

/** Spotlight dims every other dot and the referee to this opacity. */
export const SPOTLIGHT_DIM = 0.35;
/** Spotlight stays on this long (match seconds) after a big moment of the selected player (guess). */
export const SPOTLIGHT_MOMENT_S = 7;
/** Importance at or above which a selected player's event turns the spotlight on ("ecstatic" band). */
export const SPOTLIGHT_MIN_IMPORTANCE = 0.8;
/** After clicking a player, the others stay fully dimmed this long (real milliseconds, guess). */
export const SPOTLIGHT_ON_SELECT_MS = 1500;
/** The other dots then ease back to full color over this long (real time after a click, guess). */
export const SPOTLIGHT_FADE_MS = 1000;
/** After a big moment the spotlight eases out over its last this-many match seconds (guess). */
export const SPOTLIGHT_MOMENT_FADE_S = 1.5;

/** Dot sizes in meters (viewBox units). 26 px dot and 12 px ball at the reference size of ~7 px/m. */
export const DOT_R = 1.75;
/**
 * Ball radius (owner, Oct 26: bigger and patterned so it is easy to find; still smaller than a
 * player dot). About 15 px at the reference size, against 26 px for a dot.
 */
export const BALL_R = 1.05;
/*
 * The ball is drawn at its true position, also when carried (it then covers the shirt number).
 * Drawing a carried ball on the dot's rim was tried and dropped (owner, Oct 26): following the
 * carrier's direction made it swing around the dot on every touch and look glitchy.
 */
export const REF_HALF = 0.9;

/**
 * Movement arrows: a small, sharp, filled triangle growing out of a moving dot's outline (lime out
 * of the followed player's ring), pointing where the player is heading (from their last second of movement). Direction only, one fixed size. Always on for
 * the followed player (lime, drawn above every dot) and for the ARROW_NEAREST players nearest them
 * within ARROW_NEAR_MAX_DIST metres, the ones reacting to them; the "All movement arrows" setting
 * (off by default) adds everyone else. Hidden below MOTION_MIN_SPEED (standing or walking).
 * Tried and dropped (owner, Oct 26): an arrow with a shaft, speed lines, and an arc on the dot's
 * front edge (too busy).
 */
export const ARROW_NEAREST = 5;
export const ARROW_NEAR_MAX_DIST = 25; // m
export const MOTION_MIN_SPEED = 1.2; // m/s

/**
 * Shot flight (owner, Oct 26): positions.json has one ball sample a second, so a shot would glide
 * from the kick to the target over a whole second. Instead the ball flies the shot's own
 * `from` -> `to` line at its `speed_kmh` (about 0.4 s), and the GOAL banner and score wait until it
 * lands. A flight is capped just under one second so the ball is back on its 1 Hz track at the next sample. */
export const SHOT_FLIGHT_MAX_S = 0.9;

/** Selected player's trail length in match seconds (guess). */
export const TRAIL_S = 5;
/** Sent-off dot fades out over this many match seconds once it stops at the touchline. */
export const SENT_OFF_FADE_S = 2;

/** How long action visuals stay on the pitch, in match seconds (guesses). */
export const VISUAL_S = {
  pass: 1.4,
  shot: 3,
  flash: 1.2,
  pulse: 1.2,
  ratingPop: 1.8,
  goalBanner: 7,
  penaltyBanner: 6,
  cardCaption: 5,
} as const;

/**
 * Rating pops: the selected player pops on every change; other players only on changes at least
 * this big, so routine +0.01 duel credit doesn't clutter the action (guess, tune by eye).
 */
export const POP_MIN_DELTA_OTHERS = 0.05;

/** Commentary chunk length in match seconds and the line rules from ARCHITECTURE ("Commentary cadence"). */
export const CHUNK_S = 60;
export const MAX_CHUNK = 89;
export const LINE_MIN_GAP_S = 5;
export const LINE_MAX_SILENCE_S = 15;
export const LATE_LINE_DROP_S = 10;

/**
 * Static title-race table before matchday 38 (owner decision Oct 26): Redmond lead by a point, so
 * Azure must win; a draw or a loss leaves Redmond champions. Fictional, never simulated.
 */
export const STANDINGS = { rdm: { pos: "1st", pts: 85 }, azc: { pos: "2nd", pts: 84 } } as const;

/**
 * Goalkeeper kits (owner decision Oct 26), used instead of meta.json's keeper_color: gold and pink
 * stay distinct from both kits, each other, the pitch, the white ball and the black referee under
 * normal vision and protan, deutan and tritan color blindness (simulated worst case dE 31.9; the
 * old neon yellow / orange pair fell to 14.9, yellow against the ball for tritan).
 */
export const KEEPER_COLORS = { azc: "#FACC15", rdm: "#F472B6" } as const;

export const COLORS = {
  azc: "#3B82F6",
  rdm: "#E5484D",
  pitch: "#2E5A30",
  lime: "#A3E635",
} as const;

/**
 * Crowd audio (owner, Oct 26). Azure City is the home crowd. Every gain and timing here is a
 * guess, tuned by ear; volumes are 0 to 1 before the master gain.
 * Clips: wordless CC0 recordings from Freesound (see web/public/audio/crowd/CREDITS.md), with
 * the murmur, goal roar, near-miss and cheer taken from a real football stadium.
 * `offset` skips to where the sound rises, so its loud part lands about 0.3 to 0.8 s after the
 * moment (measured from each clip's loudness curve); `play` is how long a reaction lasts before it
 * fades out; `norm` evens out the recordings' levels (measured, so the gains below compare).
 */
export const CROWD_CLIPS = {
  // the four "stadium-" clips are trimmed from one real football stadium recording; each file starts where its sound rises
  murmur: { file: "stadium-murmur.m4a", offset: 0, play: 0, norm: 2.36 }, // 64 s, tail blended into head so it loops seamlessly
  roar: { file: "stadium-goal.m4a", offset: 0, play: 12, norm: 0.9 }, // full roar 0.25 s in; the loudest sound in the match (owner)
  cheer: { file: "stadium-cheer.m4a", offset: 0, play: 5, norm: 0.71 },
  ooh: { file: "stadium-chance-missed.m4a", offset: 0, play: 4.5, norm: 0.78 }, // swells to its peak about 0.8 s in
  conceded: { file: "stadium-conceded.m4a", offset: 1, play: 8, norm: 0.6 }, // the loudest "OHHH" take; skipping 1 s starts it already loud, peak 1.7 s in
  gasp: { file: "gsc-gasp-voiced.mp3", offset: 0.4, play: 2, norm: 1.25 },
  boo: { file: "gsc-booing.mp3", offset: 0.8, play: 4, norm: 1 },
  whistle: { file: "rosa-ref-whistle.mp3", offset: 0, play: 0.54, norm: 1 }, // one real blast, about 2.4 kHz
} as const;
export type CrowdClip = keyof typeof CROWD_CLIPS;

export const CROWD = {
  /** Master volume for everything: the crowd and the commentary voice share it, so Mute silences both. */
  master: 0.7,
  /** Commentary voice level before the master gain at midfield (guess, tune by ear). It rises toward the goals like the crowd. */
  voiceGain: 1.1, // owner: louder (was 0.8)
  /** Extra voice level with the ball on a goal line: `voiceGain * (1 + voiceDangerBoost * danger)` (danger 0..1). */
  voiceDangerBoost: 0.5,
  /** Extra factor for big lines (importance >= 0.8: goals, cards involving the player). */
  voiceBigBoost: 1.3,
  /** A line that waited for the previous one to finish is dropped if it waited longer than this (seconds); guess. */
  voiceQueueMaxS: 6,
  /**
   * Ducking: while a commentary clip plays, the crowd drops to `duck` of its volume (`duckGoal`
   * under a goal roar, so it still comes through), in `duckAttackS`, and comes back over
   * `duckReleaseS` after the line ends.
   */
  duck: 1, // owner (Oct 27): no ducking, lowering the crowd under the voice broke immersion (was 0.35)
  duckGoal: 1, // was 0.6
  /** The whole crowd (murmur, roars, reactions) at a steady level all match, under the voice (owner, Oct 27: 60%, so the voice is easy to hear). */
  crowdLevel: 0.6,
  duckAttackS: 0.2,
  duckReleaseS: 1,
  /** Murmur: always on; swells when the ball is near a goal, more for Azure's attacks. */
  murmurBase: 0.35,
  murmurHomeAttack: 0.35, // extra when the ball is deep in Redmond's half (x 70 -> 95 m)
  murmurAwayAttack: 0.15, // extra (nerves) when Redmond attack (x 35 -> 10 m)
  goalHome: 1,
  /**
   * Redmond goal: an anguished stadium "OHHH" at `goalAway`, then the stunned home crowd stays
   * quiet (murmur at `goalAwayHush` of its level for `goalAwayHushS`, easing back over the last
   * `goalAwayRecoverS`).
   */
  goalAway: 1,
  goalAwayHush: 0.35,
  goalAwayHushS: 10,
  goalAwayRecoverS: 3,
  /** Azure shots that miss: gain = shotHomeBase + importance, capped at shotHomeMax. */
  shotHomeBase: 0.25,
  shotHomeMax: 0.8,
  /** Redmond shots draw a nervous gasp only from this importance up. */
  shotAwayMinImportance: 0.4,
  shotAway: 0.35,
  penalty: 0.9,
  yellow: 0.6,
  red: 1,
  /** A red card's boos or cheers last longer than a yellow's. */
  redPlay: 7,
  /** Loud enough to cut through the murmur; the crowd's boos or cheers start `afterWhistleS` later. */
  whistle: 0.6,
  afterWhistleS: 0.4,
  /** Full time: three blasts this far apart (seconds). */
  finalWhistleGap: 0.45,
  /** At this speed and above only goals and red cards draw a reaction (else constant noise). */
  fastRate: 10,
  /**
   * Above 1x a reaction lasts its 1x length divided by the speed (the clip keeps its normal pitch,
   * only its length is cut), but never less than `minFastPlayS`, so it still reads as a roar or boo.
   */
  minFastPlayS: 2.5,
  /** Reaction clips fade out over this many seconds (on seek, and at the end of `play`). */
  fadeS: 0.6,
} as const;
