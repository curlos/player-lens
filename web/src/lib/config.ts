/**
 * Frontend knobs in one place. Values marked "guess" are presentation choices, tune freely;
 * everything else comes from specs/frontend.md.
 */

/** The only playback rates (owner decision Oct 26). */
export const SPEEDS = [1, 2, 4, 10, 30] as const;
export type Speed = (typeof SPEEDS)[number];

/** Highlight chips and timeline clicks seek this many seconds before the event. */
export const HIGHLIGHT_LEAD_S = 8;
/** Arrow keys seek by this many seconds. */
export const ARROW_SEEK_S = 5;

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
