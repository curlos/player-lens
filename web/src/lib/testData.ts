/** Test helper: builds MatchData from the committed hero files on disk (no network). */
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { buildMatch, type MatchData } from "./match";

export function loadFixture(matchId = "md38_title_decider"): MatchData {
  const dir = join(__dirname, "..", "..", "..", "data", "matches", matchId);
  const read = (f: string) => JSON.parse(readFileSync(join(dir, f), "utf8"));
  return buildMatch(read("meta.json"), read("events.json"), read("ratings.json"), read("positions.json"));
}
