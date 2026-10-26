/* Generated from contracts/events.schema.json by scripts/gen-types.mjs. Do not edit by hand. */

export type MatchId = string;
export type SchemaVersion = number;
export type Id = string;
export type T = number;
export type Type =
  | "pass"
  | "key_pass"
  | "shot"
  | "goal"
  | "save"
  | "tackle"
  | "interception"
  | "block"
  | "clearance"
  | "aerial_duel"
  | "dribble"
  | "foul"
  | "handball"
  | "offside"
  | "card_yellow"
  | "card_red"
  | "pressure"
  | "pressure_regain"
  | "counterpress"
  | "recovery_run"
  | "marking_denial"
  | "decoy_run"
  | "shape_check"
  | "error_leading_to_goal"
  | "big_chance_missed"
  | "injury"
  | "gk_claim"
  | "gk_sweep"
  | "kickoff"
  | "throw_in"
  | "goal_kick"
  | "corner"
  | "free_kick"
  | "penalty";
export type Team = "azc" | "rdm";
export type Player = string;
export type Other = string | null;
export type X = number;
export type Y = number;
export type Outcome = "success" | "fail" | "goal" | "saved" | "blocked" | "off_target" | "post" | "awarded" | "none";
export type Xg = number | null;
export type SpeedKmh = number | null;
export type Importance = number;
export type Azc = number;
export type Rdm = number;
export type Related = string[] | null;
export type Events = Event[];

export interface EventsFile {
  match_id: MatchId;
  schema_version?: SchemaVersion;
  events: Events;
}
/**
 * One simulator event. ``from``/``to`` are Python keywords, so the attributes carry a trailing underscore.
 */
export interface Event {
  id: Id;
  t: T;
  type: Type;
  team: Team;
  player: Player;
  other?: Other;
  from?: Point | null;
  to?: Point | null;
  outcome: Outcome;
  xg?: Xg;
  speed_kmh?: SpeedKmh;
  importance: Importance;
  score: Score;
  related?: Related;
}
/**
 * A pitch point in meters (origin top-left).
 */
export interface Point {
  x: X;
  y: Y;
}
export interface Score {
  azc: Azc;
  rdm: Rdm;
}
