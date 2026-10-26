/**
 * Match data: loads the four files and builds every lookup once, so per-frame reads are
 * O(1) or O(log n) (specs/frontend.md, "Data loading"). Nothing here computes a rating,
 * an xG or an importance: those come from the files as is.
 */
import type {
  EventsFile,
  MatchEvent,
  MatchPlayer,
  MatchSummary,
  MatchTeam,
  Meta,
  PositionsFile,
  RatingEntry,
  RatingsFile,
  TeamId,
} from "../types";
import { lastIndexAtOrBefore } from "./format";

export interface PlayerInfo extends MatchPlayer {
  team: TeamId;
  teamName: string;
  abbr: string;
  isKeeper: boolean;
}

export interface Track {
  /** Decimeters, x at 2i and y at 2i+1 for second i. */
  xy: Int16Array;
  /** Activity index per second (players and referee only). */
  act: Uint8Array | null;
}

export type HighlightKind = "goal" | "yellow" | "red" | "penalty";

export interface Highlight {
  id: string;
  t: number;
  kind: HighlightKind;
  team: TeamId;
  player: string;
  event: MatchEvent;
}

export interface MatchData {
  id: string;
  meta: Meta;
  duration: number;
  seconds: number;
  teams: Record<TeamId, MatchTeam>;
  players: Map<string, PlayerInfo>;
  playerIds: string[];
  tracks: Map<string, Track>;
  /** Every event except shape checks (never shown), sorted by t. */
  events: MatchEvent[];
  eventById: Map<string, MatchEvent>;
  /** Per player: rating entries with a non-zero delta, sorted by t. */
  ratingLog: Map<string, RatingEntry[]>;
  /** Every rating entry with a non-zero delta, sorted by t (for rating pops). */
  ratingChanges: RatingEntry[];
  ratingStart: number;
  /** Goal events (type "goal") in order; the score after each is on the event. */
  goals: MatchEvent[];
  /** Goals, cards and the penalty award, for the highlights row and the timeline. */
  highlights: Highlight[];
  /** Per sent-off player: red-card time and when the dot reaches the touchline and stops. */
  sentOff: Map<string, { cardT: number; stopT: number }>;
  /** Per player: cumulative distance in meters at the end of each second. */
  distance: Map<string, Float32Array>;
}

/** GET /matches: the library list (Phase 2: answered by the Vite dev plugin). */
export async function fetchMatchList(): Promise<MatchSummary[]> {
  const res = await fetch("/matches");
  if (!res.ok) throw new Error(`GET /matches failed: ${res.status}`);
  return res.json();
}

async function getJson<T>(url: string): Promise<T> {
  const res = await fetch(url);
  if (!res.ok) throw new Error(`GET ${url} failed: ${res.status}`);
  return res.json() as Promise<T>;
}

/** Fetches the four static files in parallel and builds the lookups. */
export async function loadMatch(matchId: string): Promise<MatchData> {
  const base = `/data/matches/${matchId}`;
  const [meta, events, ratings, positions] = await Promise.all([
    getJson<Meta>(`${base}/meta.json`),
    getJson<EventsFile>(`${base}/events.json`),
    getJson<RatingsFile>(`${base}/ratings.json`),
    getJson<PositionsFile>(`${base}/positions.json`),
  ]);
  return buildMatch(meta, events, ratings, positions);
}

export function buildMatch(meta: Meta, eventsFile: EventsFile, ratingsFile: RatingsFile, positions: PositionsFile): MatchData {
  const teams = { azc: meta.teams.find((t) => t.id === "azc")!, rdm: meta.teams.find((t) => t.id === "rdm")! };
  const players = new Map<string, PlayerInfo>();
  for (const team of meta.teams) {
    for (const p of team.players) {
      players.set(p.id, { ...p, team: team.id, teamName: team.name, abbr: team.abbr, isKeeper: p.position === "GK" });
    }
  }

  const tracks = new Map<string, Track>();
  for (const e of positions.entities) {
    tracks.set(e.id, { xy: Int16Array.from(e.xy), act: e.act ? Uint8Array.from(e.act) : null });
  }

  const allEvents = [...eventsFile.events].sort((a, b) => a.t - b.t);
  const events = allEvents.filter((e) => e.type !== "shape_check");
  const eventById = new Map(allEvents.map((e) => [e.id, e]));

  const ratingLog = new Map<string, RatingEntry[]>();
  for (const id of players.keys()) ratingLog.set(id, []);
  const ratingChanges: RatingEntry[] = [];
  for (const r of [...ratingsFile.entries].sort((a, b) => a.t - b.t)) {
    if (r.delta === 0) continue; // silent entries (shape_no_change) are never shown
    ratingLog.get(r.player)?.push(r);
    ratingChanges.push(r);
  }

  const goals = events.filter((e) => e.type === "goal");
  const highlights = buildHighlights(events);

  const duration = meta.duration_s ?? 5400;
  const sentOff = new Map<string, { cardT: number; stopT: number }>();
  const sentOffAct = meta.activities.indexOf("sent_off");
  for (const e of events) {
    if (e.type !== "card_red") continue;
    const track = tracks.get(e.player);
    sentOff.set(e.player, { cardT: e.t, stopT: track ? findStop(track, e.t, sentOffAct, positions.seconds) : e.t });
  }

  const distance = new Map<string, Float32Array>();
  for (const id of players.keys()) {
    const track = tracks.get(id);
    if (track) distance.set(id, cumulativeDistance(track.xy, positions.seconds));
  }

  return {
    id: meta.match_id,
    meta,
    duration,
    seconds: positions.seconds,
    teams,
    players,
    playerIds: [...players.keys()],
    tracks,
    events,
    eventById,
    ratingLog,
    ratingChanges,
    ratingStart: ratingsFile.start ?? 6.0,
    goals,
    highlights,
    sentOff,
    distance,
  };
}

/**
 * Goals, yellow cards, red cards and penalties in time order. A second yellow and its red card
 * share a second; only the red chip is kept so the row doesn't list the same booking twice.
 */
export function buildHighlights(events: MatchEvent[]): Highlight[] {
  const kinds: Record<string, HighlightKind> = { goal: "goal", card_yellow: "yellow", card_red: "red", penalty: "penalty" };
  const reds = new Set(events.filter((e) => e.type === "card_red").map((e) => `${e.player}@${e.t}`));
  return events
    .filter((e) => kinds[e.type] && !(e.type === "card_yellow" && reds.has(`${e.player}@${e.t}`)))
    .map((e) => ({ id: e.id, t: e.t, kind: kinds[e.type], team: e.team, player: e.player, event: e }));
}

/** The sent-off walk ends on the bottom touchline (y = 68 m); within 1 m counts as arrived. */
const SENT_OFF_TOUCHLINE_DM = 670;

/** First second after the red card where the player is on the touchline (sent_off) and no longer moving. */
function findStop(track: Track, cardT: number, sentOffAct: number, seconds: number): number {
  for (let s = Math.ceil(cardT); s < seconds - 1; s++) {
    const still = track.xy[2 * s] === track.xy[2 * s + 2] && track.xy[2 * s + 1] === track.xy[2 * s + 3];
    // a player can stand still for a second right after the card, before the walk starts
    const atTouchline = track.xy[2 * s + 1] >= SENT_OFF_TOUCHLINE_DM;
    if (still && atTouchline && (!track.act || sentOffAct < 0 || track.act[s] === sentOffAct)) return s;
  }
  return seconds - 1;
}

function cumulativeDistance(xy: Int16Array, seconds: number): Float32Array {
  const out = new Float32Array(seconds);
  for (let s = 1; s < seconds; s++) {
    const dx = (xy[2 * s] - xy[2 * s - 2]) / 10;
    const dy = (xy[2 * s + 1] - xy[2 * s - 1]) / 10;
    out[s] = out[s - 1] + Math.hypot(dx, dy);
  }
  return out;
}

/** Interpolated position in meters at match time t (linear between floor(t) and ceil(t)). */
export function positionAt(track: Track, t: number, seconds: number): [number, number] {
  const tt = Math.min(Math.max(t, 0), seconds - 1);
  const s0 = Math.floor(tt);
  const s1 = Math.min(s0 + 1, seconds - 1);
  const f = tt - s0;
  const x = track.xy[2 * s0] + (track.xy[2 * s1] - track.xy[2 * s0]) * f;
  const y = track.xy[2 * s0 + 1] + (track.xy[2 * s1 + 1] - track.xy[2 * s0 + 1]) * f;
  return [x / 10, y / 10];
}

/** Activity code name at second floor(t), or null for the ball. */
export function activityAt(match: MatchData, id: string, t: number): string | null {
  const track = match.tracks.get(id);
  if (!track?.act) return null;
  const s = Math.min(Math.max(Math.floor(t), 0), match.seconds - 1);
  return match.meta.activities[track.act[s]] ?? null;
}

/** Live rating: start plus the player's deltas up to t, read from the file's `rating_after`. */
export function ratingAt(match: MatchData, playerId: string, t: number): number {
  const log = match.ratingLog.get(playerId);
  if (!log) return match.ratingStart;
  const i = lastIndexAtOrBefore(log, t);
  return i < 0 ? match.ratingStart : log[i].rating_after;
}

/** Score right after the last goal at or before t. */
export function scoreAt(match: MatchData, t: number): { azc: number; rdm: number } {
  const i = lastIndexAtOrBefore(match.goals, t);
  return i < 0 ? { azc: 0, rdm: 0 } : match.goals[i].score;
}

/** Cards shown by t for one team: whether it has a yellow, and how many reds. */
export function teamCardsAt(match: MatchData, team: TeamId, t: number): { yellow: boolean; reds: number } {
  let yellow = false;
  let reds = 0;
  for (const h of match.highlights) {
    if (h.t > t) break;
    if (h.team !== team) continue;
    if (h.kind === "yellow") yellow = true;
    if (h.kind === "red") reds += 1;
  }
  return { yellow, reds };
}

/** Goals and assists by t, from the goal events (assister is `other`). */
export function goalsAndAssistsAt(match: MatchData, playerId: string, t: number): { goals: number; assists: number } {
  let goals = 0;
  let assists = 0;
  for (const g of match.goals) {
    if (g.t > t) break;
    if (g.player === playerId) goals += 1;
    if (g.other === playerId) assists += 1;
  }
  return { goals, assists };
}

/** Sum of the xG values on the player's shots up to t (the xG per shot comes from the file). */
export function xgAt(match: MatchData, playerId: string, t: number): number {
  let xg = 0;
  for (const e of match.events) {
    if (e.t > t) break;
    if (e.type === "shot" && e.player === playerId && e.xg != null) xg += e.xg;
  }
  return xg;
}

/** Distance covered in km up to t, from the 1 Hz positions. */
export function distanceKmAt(match: MatchData, playerId: string, t: number): number {
  const d = match.distance.get(playerId);
  if (!d) return 0;
  return d[Math.min(Math.max(Math.floor(t), 0), d.length - 1)] / 1000;
}

/** Events in the half-open window (t - span, t], via binary search on the sorted list. */
export function eventsInWindow(match: MatchData, t: number, span: number): MatchEvent[] {
  const end = lastIndexAtOrBefore(match.events, t);
  const out: MatchEvent[] = [];
  for (let i = end; i >= 0 && match.events[i].t > t - span; i--) out.push(match.events[i]);
  return out.reverse();
}

/**
 * Title winner after a title decider: STANDINGS plus 3 points for a win, 1 for a draw.
 * With Redmond a point ahead, only an Azure win changes the leader.
 */
export function titleWinner(
  standings: Record<TeamId, { pts: number }>,
  score: { azc: number; rdm: number },
): TeamId {
  const pts = (team: TeamId, own: number, other: number) => standings[team].pts + (own > other ? 3 : own === other ? 1 : 0);
  return pts("azc", score.azc, score.rdm) > pts("rdm", score.rdm, score.azc) ? "azc" : "rdm";
}

/**
 * The nearest player from `from` in a direction (screen axes, y down): candidates must lie ahead
 * within about 63 degrees of the direction; among them the closest wins, with sideways offset
 * counted double so a player straight ahead beats one far off to the side. Falls back to anyone
 * ahead at all.
 */
export function nearestInDirection(match: MatchData, from: string, ids: string[], [dx, dy]: [number, number], t: number): string | null {
  const origin = match.tracks.get(from);
  if (!origin) return null;
  const [ox, oy] = positionAt(origin, t, match.seconds);
  let best: { id: string; score: number; inCone: boolean } | null = null;
  for (const id of ids) {
    if (id === from) continue;
    const track = match.tracks.get(id);
    if (!track) continue;
    const [x, y] = positionAt(track, t, match.seconds);
    const ahead = (x - ox) * dx + (y - oy) * dy;
    const side = Math.abs((x - ox) * dy - (y - oy) * dx);
    if (ahead <= 0.3) continue;
    const inCone = side <= ahead * 2;
    const score = ahead + 2 * side;
    if (!best || (inCone && !best.inCone) || (inCone === best.inCone && score < best.score)) best = { id, score, inCone };
  }
  return best?.id ?? null;
}

/** Display string for a player id: "#9 G. Lima" (used by highlights and reason text). */
export function playerLabel(match: MatchData, id: string | null | undefined): string {
  const p = id ? match.players.get(id) : undefined;
  return p ? `#${p.number} ${p.name}` : "";
}
