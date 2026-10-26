/* Generated from contracts/meta.schema.json by scripts/gen-types.mjs. Do not edit by hand. */

export type MatchId = string;
export type SchemaVersion = number;
export type Label = string;
export type Blurb = string | null;
export type Matchday = number;
export type Seed = number;
export type Hero = boolean;
export type TitleDecider = boolean;
export type DurationS = number;
export type Azc = number;
export type Rdm = number;
export type DefaultPlayer = string;
/**
 * @minItems 2
 * @maxItems 2
 */
export type Teams = [MatchTeam, MatchTeam];
export type Id = "azc" | "rdm";
export type Name = string;
export type Abbr = string;
export type Formation = "4-3-3" | "4-4-2";
export type Color = string;
export type KeeperColor = string;
/**
 * @minItems 11
 * @maxItems 11
 */
export type Players = [
  MatchPlayer,
  MatchPlayer,
  MatchPlayer,
  MatchPlayer,
  MatchPlayer,
  MatchPlayer,
  MatchPlayer,
  MatchPlayer,
  MatchPlayer,
  MatchPlayer,
  MatchPlayer
];
export type Id1 = string;
export type Name1 = string;
export type FirstName = string | null;
/**
 * Where a player's name comes from (specs/roster-generator.md); fictional players, real name pools.
 */
export type Nationality =
  "England" | "Spain" | "Brazil" | "France" | "Germany" | "Portugal" | "Austria" | "Netherlands" | "Italy";
export type Number = number;
export type Position = "GK" | "CB" | "FB" | "DM" | "CM" | "AM" | "W" | "ST";
export type Slot = string;
export type Ovr = number;
export type Gender = "male";
export type Temperament = "calm" | "normal" | "hot-headed";
export type Pace = number;
export type Passing = number;
export type Vision = number;
export type Finishing = number;
export type Dribbling = number;
export type Defending = number;
export type Positioning = number;
export type Composure = number;
export type Strength = number;
export type WorkRate = number;
export type Stamina = number;
export type SetPieces = number;
export type ShotStopping = number | null;
/**
 * @minItems 1
 */
export type Activities = [string, ...string[]];
/**
 * @minItems 24
 * @maxItems 24
 */
export type EntityOrder = [
  string,
  string,
  string,
  string,
  string,
  string,
  string,
  string,
  string,
  string,
  string,
  string,
  string,
  string,
  string,
  string,
  string,
  string,
  string,
  string,
  string,
  string,
  string,
  string
];

/**
 * meta.json: everything the UI needs before playback.
 */
export interface Meta {
  match_id: MatchId;
  schema_version?: SchemaVersion;
  label: Label;
  blurb?: Blurb;
  matchday: Matchday;
  seed: Seed;
  hero: Hero;
  title_decider: TitleDecider;
  duration_s?: DurationS;
  score: Score;
  default_player: DefaultPlayer;
  teams: Teams;
  activities: Activities;
  entity_order: EntityOrder;
}
export interface Score {
  azc: Azc;
  rdm: Rdm;
}
export interface MatchTeam {
  id: Id;
  name: Name;
  abbr: Abbr;
  formation: Formation;
  color: Color;
  keeper_color: KeeperColor;
  players: Players;
}
/**
 * A roster entry as copied into meta.json (the frontend never reads world.json).
 */
export interface MatchPlayer {
  id: Id1;
  name: Name1;
  first_name?: FirstName;
  nationality?: Nationality | null;
  number: Number;
  position: Position;
  slot: Slot;
  ovr: Ovr;
  gender: Gender;
  temperament: Temperament;
  attributes: Attributes;
}
/**
 * Outfield attributes, 25-99. ``shot_stopping`` is for goalkeepers only.
 */
export interface Attributes {
  pace: Pace;
  passing: Passing;
  vision: Vision;
  finishing: Finishing;
  dribbling: Dribbling;
  defending: Defending;
  positioning: Positioning;
  composure: Composure;
  strength: Strength;
  work_rate: WorkRate;
  stamina: Stamina;
  set_pieces: SetPieces;
  shot_stopping?: ShotStopping;
}
