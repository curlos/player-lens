/* Generated from contracts/positions.schema.json by scripts/gen-types.mjs. Do not edit by hand. */

export type MatchId = string;
export type SchemaVersion = number;
export type Hz = 1;
export type Unit = "dm";
export type Seconds = number;
/**
 * @minItems 24
 * @maxItems 24
 */
export type Entities = [
  EntityTrack,
  EntityTrack,
  EntityTrack,
  EntityTrack,
  EntityTrack,
  EntityTrack,
  EntityTrack,
  EntityTrack,
  EntityTrack,
  EntityTrack,
  EntityTrack,
  EntityTrack,
  EntityTrack,
  EntityTrack,
  EntityTrack,
  EntityTrack,
  EntityTrack,
  EntityTrack,
  EntityTrack,
  EntityTrack,
  EntityTrack,
  EntityTrack,
  EntityTrack,
  EntityTrack
];
export type Id = string;
export type Xy = number[];
export type Act = number[] | null;

export interface PositionsFile {
  match_id: MatchId;
  schema_version?: SchemaVersion;
  hz?: Hz;
  unit?: Unit;
  seconds: Seconds;
  entities: Entities;
}
/**
 * One entity's samples. ``xy`` is flat integer decimeters [x0, y0, x1, y1, ...]; ``act`` indexes meta.activities.
 */
export interface EntityTrack {
  id: Id;
  xy: Xy;
  act?: Act;
}
