/* Generated from contracts/ratings.schema.json by scripts/gen-types.mjs. Do not edit by hand. */

export type MatchId = string;
export type SchemaVersion = number;
export type Start = number;
export type Id = string;
export type T = number;
export type Player = string;
export type EventId = string;
export type RawDelta = number;
export type Scale = number;
export type Delta = number;
export type RatingAfter = number;
export type ReasonCode = string;
export type OffBall = boolean;
export type Entries = RatingEntry[];

export interface RatingsFile {
  match_id: MatchId;
  schema_version?: SchemaVersion;
  start?: Start;
  entries: Entries;
}
/**
 * One rating change. A player's rating at time t is 6.0 plus the sum of their deltas up to t.
 */
export interface RatingEntry {
  id: Id;
  t: T;
  player: Player;
  event_id: EventId;
  raw_delta: RawDelta;
  scale: Scale;
  delta: Delta;
  rating_after: RatingAfter;
  reason_code: ReasonCode;
  values?: Values;
  off_ball: OffBall;
}
export interface Values {
  [k: string]: string | number | boolean;
}
