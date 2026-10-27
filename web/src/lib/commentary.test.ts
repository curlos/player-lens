import { describe, expect, it } from "vitest";
import { buildLines, getCommentaryChunk, getTrace } from "./commentary";
import { LINE_MAX_SILENCE_S, LINE_MIN_GAP_S } from "./config";
import { shownAt } from "./match";
import { loadFixture } from "./testData";

const match = loadFixture();

describe("template commentary placeholder", () => {
  const lines = buildLines(match, "azc_09", "casual", "en");

  it("produces CommentaryLine-shaped template lines for the player", () => {
    expect(lines.length).toBeGreaterThan(300);
    for (const l of lines) {
      expect(l.fact_check).toBe("template");
      expect(l.audio_url).toBeNull();
      expect(l.player).toBe("azc_09");
      expect(l.t).toBeGreaterThanOrEqual(0);
      expect(l.t).toBeLessThanOrEqual(5400);
      expect(l.text).not.toMatch(/undefined|NaN/);
    }
    expect(new Set(lines.map((l) => l.id)).size).toBe(lines.length);
  });

  it("keeps the cadence: min gap except for big moments, no silence much over the limit", () => {
    for (let i = 1; i < lines.length; i++) {
      const gap = lines[i].t - (lines[i - 1].t + lines[i - 1].duration);
      if (lines[i].type === "reaction") expect(gap).toBeGreaterThanOrEqual(0);
      else if (lines[i].importance < 0.8) expect(gap).toBeGreaterThanOrEqual(LINE_MIN_GAP_S - 0.5);
      expect(gap).toBeLessThanOrEqual(LINE_MAX_SILENCE_S + 1);
    }
  });

  it("follows every goal with a reaction line 8 s later", () => {
    for (const g of match.goals) expect(lines.some((l) => l.type === "reaction" && l.t === g.t + 8)).toBe(true);
  });

  it("calls the star's goals", () => {
    expect(lines.some((l) => l.type === "goal" && l.t === shownAt(match, 2327) && l.t > 2327 && l.text.startsWith("GOAL!"))).toBe(true);
  });

  it("slices 1-minute chunks and returns a single Template trace step", async () => {
    const chunk = await getCommentaryChunk(match, "azc_09", "analyst", "es", 38);
    expect(chunk.chunk).toBe(38);
    expect(chunk.lines.every((l) => l.t >= 38 * 60 && l.t < 39 * 60)).toBe(true);
    const trace = await getTrace(chunk.lines[0].id);
    expect(trace?.steps).toHaveLength(1);
    expect(trace?.steps[0].agent).toBe("Template");
  });
});
