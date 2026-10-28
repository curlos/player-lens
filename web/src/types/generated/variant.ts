/* Generated from contracts/variant.schema.json by scripts/gen-types.mjs. Do not edit by hand. */

export type MomentId = string;
export type Mode = "casual" | "analyst";
export type Lang = "en" | "es";
export type Text = string;

/**
 * The Personalizer's version of a checked line for one mode and language.
 */
export interface Variant {
  moment_id: MomentId;
  mode: Mode;
  lang: Lang;
  text: Text;
}
