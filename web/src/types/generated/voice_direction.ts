/* Generated from contracts/voice_direction.schema.json by scripts/gen-types.mjs. Do not edit by hand. */

export type MomentId = string;
export type Mode = "casual" | "analyst";
export type Lang = "en" | "es";
export type Pauses = number[];
/**
 * @maxItems 2
 */
export type Emphasis = [] | [string] | [string, string];
export type Rate = "slow" | "normal" | "fast";
export type Style = string;

/**
 * The Voice Director's speaking instructions for one variant; code turns them into SSML.
 */
export interface VoiceDirection {
  moment_id: MomentId;
  mode: Mode;
  lang: Lang;
  pauses?: Pauses;
  emphasis?: Emphasis;
  rate?: Rate;
  style?: Style;
}
