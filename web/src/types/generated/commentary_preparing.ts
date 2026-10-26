/* Generated from contracts/commentary_preparing.schema.json by scripts/gen-types.mjs. Do not edit by hand. */

export type Status = "preparing";
export type RetryAfter = number;

/**
 * GET /commentary 202 response while a chunk is generating.
 */
export interface ChunkPreparing {
  status?: Status;
  retry_after: RetryAfter;
}
