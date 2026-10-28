/* Generated from contracts/moment.schema.json by scripts/gen-types.mjs. Do not edit by hand. */

export type MomentId = string;
export type T = number;
export type Trigger = string;
export type Importance = number;
export type Tone = "calm" | "building" | "excited" | "tense" | "relieved" | "analytical";
/**
 * @minItems 1
 */
export type FactIds = [string, ...string[]];
export type Why = string;

/**
 * A scheduled commentary moment: when code decided a line happens, plus the LLM's tone and reason.
 */
export interface Moment {
  moment_id: MomentId;
  t: T;
  trigger: Trigger;
  importance: Importance;
  tone?: Tone;
  fact_ids: FactIds;
  why?: Why;
}
