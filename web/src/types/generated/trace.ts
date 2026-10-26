/* Generated from contracts/trace.schema.json by scripts/gen-types.mjs. Do not edit by hand. */

export type LineId = string;
/**
 * @minItems 1
 */
export type Steps = [TraceStep, ...TraceStep[]];
export type Agent = "Interpreter" | "Moments" | "Commentator" | "Fact Guard" | "Personalizer" | "Voice" | "Template";
export type Summary = string | null;
export type FactIds = string[] | null;
export type Why = string | null;
export type Text = string | null;
export type FactCheck = ("pass" | "fixed" | "removed" | "template") | null;
export type Issues = string[] | null;
export type Before = string | null;
export type After = string | null;
export type Mode = ("casual" | "analyst") | null;
export type Lang = ("en" | "es") | null;
export type DurationS = number | null;
export type Style = string | null;
export type Reason = ("cap" | "failure") | null;
export type Events = string[];

/**
 * GET /agents/trace response.
 */
export interface Trace {
  line_id: LineId;
  steps: Steps;
  events: Events;
}
/**
 * One agent's step in "How this was made". Fields beyond ``agent`` depend on the agent.
 */
export interface TraceStep {
  agent: Agent;
  summary?: Summary;
  fact_ids?: FactIds;
  why?: Why;
  text?: Text;
  fact_check?: FactCheck;
  issues?: Issues;
  before?: Before;
  after?: After;
  mode?: Mode;
  lang?: Lang;
  duration_s?: DurationS;
  style?: Style;
  reason?: Reason;
}
