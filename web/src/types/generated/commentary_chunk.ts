/* Generated from contracts/commentary_chunk.schema.json by scripts/gen-types.mjs. Do not edit by hand. */

export type Match = string;
export type Player = string;
export type Mode = "casual" | "analyst";
export type Lang = "en" | "es";
export type Chunk = number;
export type Status = "ready";
export type Id = string;
export type T = number;
export type Duration = number;
export type Player1 = string;
export type Type = string;
export type Importance = number;
export type Text = string;
export type AudioUrl = string | null;
export type FactCheck = "pass" | "fixed" | "removed" | "template";
export type Lines = CommentaryLine[];

/**
 * GET /commentary response for one cached 1-minute chunk.
 */
export interface CommentaryChunk {
  match: Match;
  player: Player;
  mode: Mode;
  lang: Lang;
  chunk: Chunk;
  status?: Status;
  lines: Lines;
}
/**
 * One line, shaped so a studio could render it as a synchronized overlay.
 */
export interface CommentaryLine {
  id: Id;
  t: T;
  duration: Duration;
  player: Player1;
  type: Type;
  importance: Importance;
  text: Text;
  audio_url?: AudioUrl;
  fact_check: FactCheck;
}
