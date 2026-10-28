/**
 * Crowd director (specs/match-rules.md, "Crowd sound"): turns the match into crowd cues. Pure and
 * deterministic, no Web Audio here; `audio.ts` plays what this returns. Azure City is the home
 * crowd: it roars at Azure's goals, lets out an anguished "OHHH" at Redmond's and then goes
 * quiet, cheers Redmond's cards and boos Azure's. The referee's whistle sounds for kickoffs,
 * cards, the penalty and full time (cards and the penalty at every speed); not for every foul,
 * so it stays a signal rather than a constant peep.
 */
import { CROWD, CROWD_CLIPS, type CrowdClip } from "./config";
import { ballAt, eventsInWindow, goalRevealT, type MatchData } from "./match";
import type { MatchEvent } from "../types";

export type CrowdSound = CrowdClip | "whistleLong";

export interface CrowdCue {
  /** Match time the cue belongs to (a goal's is when the ball lands). */
  t: number;
  sound: Exclude<CrowdSound, "murmur">;
  gain: number;
  /** Seconds before the clip fades out (whistles have their own fixed length). */
  play?: number;
  /** The event that caused it ("full_time" for the final whistle). */
  source: string;
}

/** Cues for one event, in the order they should sound (whistle first). */
function cuesFor(match: MatchData, e: MatchEvent): CrowdCue[] {
  const home = e.team === "azc";
  const imp = e.importance ?? 0;
  const cue = (sound: CrowdCue["sound"], gain: number, play?: number, t = e.t): CrowdCue => ({ t, sound, gain, play, source: e.id });
  const react = e.t + CROWD.afterWhistleS; // the crowd answers the referee's whistle
  switch (e.type) {
    case "goal": {
      const t = goalRevealT(match, e);
      // a Redmond goal: an anguished "OHHH", then the home crowd hushes (see murmurLevel)
      return [home ? cue("roar", CROWD.goalHome, undefined, t) : cue("conceded", CROWD.goalAway, undefined, t)];
    }
    case "shot":
      if (e.outcome === "goal") return []; // the goal event reacts, when the ball lands
      if (home) return [cue("ooh", Math.min(CROWD.shotHomeBase + imp, CROWD.shotHomeMax))];
      return imp >= CROWD.shotAwayMinImportance ? [cue("gasp", CROWD.shotAway)] : [];
    case "penalty":
      return [cue("whistle", CROWD.whistle), home ? cue("cheer", CROWD.penalty, undefined, react) : cue("boo", CROWD.penalty, undefined, react)];
    case "card_yellow":
      // the crowd boos a booking against its own side and cheers one against the visitors
      return [cue("whistle", CROWD.whistle), home ? cue("boo", CROWD.yellow, undefined, react) : cue("cheer", CROWD.yellow, undefined, react)];
    case "card_red":
      return [cue("whistle", CROWD.whistle), home ? cue("boo", CROWD.red, CROWD.redPlay, react) : cue("cheer", CROWD.red, CROWD.redPlay, react)];
    case "kickoff":
      return [cue("whistle", CROWD.whistle)];
    default:
      return [];
  }
}

/** A reaction's length at `rate`: shortened with the speed, down to `minFastPlayS` (whistles keep theirs). */
function scaledPlay(c: CrowdCue, rate: number): number | undefined {
  if (rate <= 1 || c.sound === "whistle" || c.sound === "whistleLong") return c.play;
  const full = c.play ?? CROWD_CLIPS[c.sound].play;
  return Math.max(full / rate, Math.min(full, CROWD.minFastPlayS));
}

/** At 10x and 30x only these react, so fast playback isn't a wall of noise. */
const FAST_SOURCES = new Set(["goal", "card_red"]);
/** ...but the referee still whistles these at every speed (whistle only, no crowd reaction). */
const FAST_WHISTLES = new Set(["card_yellow", "penalty"]);

/**
 * Cues whose time falls in (fromT, toT], in time order. Called once per frame with the previous
 * and current clock time while playing; never across a seek (the caller skips seeks).
 */
export function crowdCues(match: MatchData, fromT: number, toT: number, rate: number): CrowdCue[] {
  if (toT <= fromT) return [];
  const fast = rate >= CROWD.fastRate;
  const out: CrowdCue[] = [];
  // a goal sounds up to a second after its event time (ball in flight), so look one second further back
  const events = eventsInWindow(match, toT, toT - fromT + 1);
  // a second yellow shares its second with the red card: only the red reacts (as in the highlights)
  const reds = new Set(events.filter((e) => e.type === "card_red").map((e) => `${e.player}@${e.t}`));
  const whistles = new Map<number, CrowdCue>(); // two decisions in one second share one whistle, the louder
  for (const e of events) {
    const whistleOnly = fast && !FAST_SOURCES.has(e.type);
    if (whistleOnly && !FAST_WHISTLES.has(e.type)) continue;
    if (e.type === "card_yellow" && reds.has(`${e.player}@${e.t}`)) continue;
    for (const c of cuesFor(match, e)) {
      if (c.t <= fromT || c.t > toT || (whistleOnly && c.sound !== "whistle")) continue;
      const cue = { ...c, play: scaledPlay(c, rate) };
      if (cue.sound === "whistle") {
        const prev = whistles.get(cue.t);
        if (prev) {
          prev.gain = Math.max(prev.gain, cue.gain); // prev is the cue already in `out`
          continue;
        }
        whistles.set(cue.t, cue);
      }
      out.push(cue);
    }
  }
  if (fromT < match.duration && toT >= match.duration) {
    out.push({ t: match.duration, sound: "whistleLong", gain: CROWD.whistle, source: "full_time" });
  }
  return out.sort((a, b) => a.t - b.t);
}

/** 0 at `a`, 1 at `b` (either direction), smooth in between. */
function ramp(x: number, a: number, b: number): number {
  const u = Math.min(Math.max((x - a) / (b - a), 0), 1);
  return u * u * (3 - 2 * u);
}

/** 1 normally; `goalAwayHush` for a while after a Redmond goal lands, easing back to 1. */
function hush(match: MatchData, t: number): number {
  const { goalAwayHush: low, goalAwayHushS: len, goalAwayRecoverS: rec } = CROWD;
  let f = 1;
  for (const g of match.goals) {
    if (g.team === "azc") continue;
    const dt = t - goalRevealT(match, g);
    if (dt >= 0 && dt < len) f = Math.min(f, low + (1 - low) * ramp(dt, len - rec, len));
  }
  return f;
}

/**
 * How close the ball is to either goal at t, 0 (midfield) to 1 (on the goal line), over the same zones the murmur
 * swells in. The commentary voice rises with it, like the crowd.
 */
export function dangerLevel(match: MatchData, t: number): number {
  if (t >= match.duration) return 0;
  const [x] = ballAt(match, t);
  return Math.max(ramp(x, 70, 95), ramp(x, 35, 10));
}

/**
 * Murmur volume at t: a steady base that swells as the ball nears either goal, hushed after a
 * Redmond goal; silent after full time.
 */
export function murmurLevel(match: MatchData, t: number): number {
  if (t >= match.duration) return 0;
  const [x] = ballAt(match, t);
  // Azure attacks left to right all match: high x is Redmond's end
  const swell = CROWD.murmurBase + CROWD.murmurHomeAttack * ramp(x, 70, 95) + CROWD.murmurAwayAttack * ramp(x, 35, 10);
  return swell * hush(match, t);
}
