/* Generated from contracts/recap.schema.json by scripts/gen-types.mjs. Do not edit by hand. */

export type Text = string;
export type AudioUrl = string | null;
export type DurationS = number | null;

/**
 * GET /recap response: the full-time paragraph for one player, mode and language.
 */
export interface Recap {
  text: Text;
  audio_url?: AudioUrl;
  duration_s?: DurationS;
}
