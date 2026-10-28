/** Contract types, generated from contracts/*.schema.json (see scripts/gen-types.mjs). */
export type { Meta, MatchTeam, MatchPlayer } from "./generated/meta";
export type { EventsFile, Event as MatchEvent, Point } from "./generated/events";
export type { RatingsFile, RatingEntry } from "./generated/ratings";
export type { PositionsFile, EntityTrack } from "./generated/positions";
export type { CommentaryChunk, CommentaryLine } from "./generated/commentary_chunk";
export type { Trace, TraceStep } from "./generated/trace";
export type { Recap } from "./generated/recap";

export type TeamId = "azc" | "rdm";
export type Mode = "casual" | "analyst";
export type Lang = "en" | "es";

/** One row of GET /matches (specs/agents-backend.md). Not a file contract, so it is typed here. */
export interface MatchSummary {
  match_id: string;
  label: string;
  blurb: string | null;
  matchday: number;
  home: string;
  away: string;
  score: { azc: number; rdm: number };
  hero: boolean;
}
