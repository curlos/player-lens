/* Generated from contracts/canonical_line.schema.json by scripts/gen-types.mjs. Do not edit by hand. */

export type MomentId = string;
export type Text = string;
export type FactIdsUsed = string[];

/**
 * The Commentator's one neutral English line for a moment.
 */
export interface CanonicalLine {
  moment_id: MomentId;
  text: Text;
  fact_ids_used?: FactIdsUsed;
}
