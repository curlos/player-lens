/* Generated from contracts/fact.schema.json by scripts/gen-types.mjs. Do not edit by hand. */

export type FactId = string;
export type T = number;
export type Kind =
  | "goal"
  | "shot"
  | "key_pass"
  | "tackle"
  | "foul"
  | "card"
  | "rating_change"
  | "pressure_regain"
  | "counterpress"
  | "recovery_run"
  | "marking_denial"
  | "decoy_run"
  | "spell"
  | "filler_stat"
  | "play";
export type PlayerId = string;
export type EventIds = string[];
export type Label = string;

/**
 * One code-built fact the commentary may cite. Numbers and names live only in ``values``.
 */
export interface Fact {
  fact_id: FactId;
  t: T;
  kind: Kind;
  player_id: PlayerId;
  event_ids: EventIds;
  values?: Values;
  label?: Label;
}
export interface Values {
  [k: string]: string | number | boolean;
}
