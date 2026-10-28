/* Generated from contracts/guard_result.schema.json by scripts/gen-types.mjs. Do not edit by hand. */

export type MomentId = string;
export type Text = string;
export type FactCheck = "pass" | "fixed" | "removed";
export type Issues = string[];
export type Before = string | null;
export type After = string | null;

/**
 * Fact Guard's verdict on one line. ``before`` and ``after`` are set only when it fixed the line.
 */
export interface GuardResult {
  moment_id: MomentId;
  text: Text;
  fact_check: FactCheck;
  issues?: Issues;
  before?: Before;
  after?: After;
}
