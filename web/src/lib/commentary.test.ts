import { afterEach, describe, expect, it, vi } from "vitest";
import { buildLines, ChunkPreparing, getCommentaryChunk, getRecap, getTrace, retimeLines } from "./commentary";
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
    vi.stubGlobal("fetch", () => Promise.reject(new TypeError("network down"))); // no backend: the offline fallback builds it locally
    const chunk = await getCommentaryChunk(match, "azc_09", "analyst", "es", 38);
    expect(chunk.chunk).toBe(38);
    expect(chunk.lines.every((l) => l.t >= 38 * 60 && l.t < 39 * 60)).toBe(true);
    const trace = await getTrace(chunk.lines[0].id);
    expect(trace?.steps).toHaveLength(1);
    expect(trace?.steps[0].agent).toBe("Template");
  });
});

afterEach(() => vi.unstubAllGlobals());

const json = (body: unknown, status = 200) => Promise.resolve(new Response(JSON.stringify(body), { status }));
const backendLine = (t: number, type = "filler") => ({
  id: `md38_title_decider.azc_09.casual.en.38.${t}`, t, duration: 3, player: "azc_09", type, importance: 0.1, text: "A line.", audio_url: null, fact_check: "pass",
});

describe("GET /commentary", () => {
  it("asks for the chunk with its key and re-times a goal line to when the ball lands", async () => {
    const fetchMock = vi.fn((_url: string) =>
      json({ match: match.id, player: "azc_09", mode: "casual", lang: "en", chunk: 38, status: "ready", lines: [backendLine(2327, "goal"), backendLine(2335, "reaction")] }),
    );
    vi.stubGlobal("fetch", fetchMock);
    const chunk = await getCommentaryChunk(match, "azc_09", "casual", "en", 38);
    expect(fetchMock).toHaveBeenCalledWith("/commentary?match=md38_title_decider&player=azc_09&mode=casual&lang=en&chunk=38");
    expect(chunk.lines[0].t).toBe(shownAt(match, 2327));
    expect(chunk.lines[0].t).toBeGreaterThan(2327); // the GOAL line waits for the ball, like the banner
    expect(chunk.lines[0].t - 2327).toBeLessThan(1);
    expect(chunk.lines[1].t).toBe(2335); // the reaction keeps its own time
  });

  it("retimeLines moves only the seconds of a goal", () => {
    const out = retimeLines(match, [backendLine(100) as never, backendLine(5318, "goal") as never]);
    expect(out[0].t).toBe(100);
    expect(out[1].t).toBeGreaterThan(5318);
  });

  it("turns a 202 into ChunkPreparing with the retry delay (the panel keeps showing 'Preparing commentary')", async () => {
    vi.stubGlobal("fetch", () => json({ status: "preparing", retry_after: 5 }, 202));
    const err = await getCommentaryChunk(match, "azc_09", "casual", "en", 38).catch((e) => e);
    expect(err).toBeInstanceOf(ChunkPreparing);
    expect(err.retryAfterS).toBe(5);
  });

  it("throws on an HTTP error so the panel retries, but falls back to local lines when the network is down", async () => {
    vi.stubGlobal("fetch", () => json({ detail: "boom" }, 500));
    await expect(getCommentaryChunk(match, "azc_09", "casual", "en", 38)).rejects.toThrow("500");
    vi.stubGlobal("fetch", () => Promise.reject(new TypeError("offline")));
    const chunk = await getCommentaryChunk(match, "azc_09", "casual", "en", 38);
    expect(chunk.lines.length).toBeGreaterThan(0);
    expect(chunk.lines.every((l) => l.fact_check === "template" && l.t >= 2280 && l.t < 2340)).toBe(true);
  });

  it("clamps the chunk index to 0..89", async () => {
    const fetchMock = vi.fn((_url: string) => json({ match: match.id, player: "azc_09", mode: "casual", lang: "en", chunk: 89, status: "ready", lines: [] }));
    vi.stubGlobal("fetch", fetchMock);
    await getCommentaryChunk(match, "azc_09", "casual", "en", 500);
    expect(String(fetchMock.mock.calls[0][0])).toContain("chunk=89");
  });
});

describe("GET /agents/trace and GET /recap", () => {
  it("returns the backend trace, and null when there is none", async () => {
    const trace = { line_id: "x.y.casual.en.1.0", steps: [{ agent: "Fact Guard", fact_check: "fixed", before: "a", after: "b" }], events: [] };
    vi.stubGlobal("fetch", () => json(trace));
    expect((await getTrace("x.y.casual.en.1.0"))?.steps[0].fact_check).toBe("fixed");
    vi.stubGlobal("fetch", () => json({ detail: "none" }, 404));
    expect(await getTrace("x.y.casual.en.1.9")).toBeNull();
    vi.stubGlobal("fetch", () => Promise.reject(new TypeError("offline")));
    expect(await getTrace("x.y.casual.en.1.9")).toBeNull();
  });

  it("recaps: the text, a 202 as ChunkPreparing, and null when unreachable", async () => {
    vi.stubGlobal("fetch", () => json({ text: "Lima finishes on 8.9.", audio_url: "/audio/abc.mp3", duration_s: 9.5 }));
    expect((await getRecap(match.id, "azc_09", "casual", "en"))?.audio_url).toBe("/audio/abc.mp3");
    vi.stubGlobal("fetch", () => json({ status: "preparing", retry_after: 3 }, 202));
    await expect(getRecap(match.id, "azc_09", "casual", "en")).rejects.toBeInstanceOf(ChunkPreparing);
    vi.stubGlobal("fetch", () => Promise.reject(new TypeError("offline")));
    expect(await getRecap(match.id, "azc_09", "casual", "en")).toBeNull();
  });
});
