/* Generated from contracts/world.schema.json by scripts/gen-types.mjs. Do not edit by hand. */

export type Seed = number;
/**
 * @minItems 2
 * @maxItems 2
 */
export type Teams = [Team, Team];
export type Id = string;
export type Name = string;
export type Abbr = string;
export type Formation = "4-3-3" | "4-4-2";
export type Color = string;
export type KeeperColor = string;
/**
 * @minItems 11
 * @maxItems 11
 */
export type Players = [Player, Player, Player, Player, Player, Player, Player, Player, Player, Player, Player];
export type Id1 = string;
export type Team1 = string;
export type Name1 = string;
export type FirstName = string;
/**
 * Where a player's name comes from (specs/roster-generator.md); fictional players, real name pools.
 */
export type Nationality =
  "England" | "Spain" | "Brazil" | "France" | "Germany" | "Portugal" | "Austria" | "Netherlands" | "Italy";
export type Number = number;
export type Position = "GK" | "CB" | "FB" | "DM" | "CM" | "AM" | "W" | "ST";
export type Slot = string;
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
export type Ovr = number;

/**
 * The whole fictional world: seed and two teams. Written to data/world.json.
 */
export interface World {
  seed: Seed;
  teams: Teams;
}
export interface Team {
  id: Id;
  name: Name;
  abbr: Abbr;
  formation: Formation;
  color: Color;
  keeper_color: KeeperColor;
  players: Players;
}
export interface Player {
  id: Id1;
  team: Team1;
  name: Name1;
  first_name: FirstName;
  nationality: Nationality;
  number: Number;
  position: Position;
  slot: Slot;
  gender?: Gender;
  temperament: Temperament;
  attributes: Attributes;
  ovr: Ovr;
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
