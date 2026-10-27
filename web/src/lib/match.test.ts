import { describe, expect, it } from "vitest";
import { minuteLabel } from "./format";
import { STANDINGS } from "./config";
import { ballAt, goalRevealT, goalsAndAssistsAt, nearestInDirection, positionAt, ratingAt, scoreAt, shownAt, shownScoreAt, teamCardsAt, titleWinner } from "./match";
import { buildMatch } from "./match";
import { loadFixture } from "./testData";

const match = loadFixture();

describe("match lookups (hero md38_title_decider)", () => {
  it("lists the hero's highlights with football minutes", () => {
    const rows = match.highlights.map((h) => `${minuteLabel(h.t)} ${h.kind} ${h.player}`);
    expect(rows.filter((r) => r.includes("goal"))).toEqual([
      "12' goal rdm_10",
      "39' goal azc_09",
      "55' goal azc_10",
      "88' goal rdm_10",
      "89' goal azc_09",
    ]);
    expect(rows).toContain("51' red azc_06");
    expect(rows).toContain("54' penalty azc_10");
    // the second yellow shares its second with the red card: only the red chip is listed
    expect(rows).not.toContain("51' yellow azc_06");
  });

  it("derives score, cards and the star's goals from t", () => {
    expect(scoreAt(match, 0)).toEqual({ azc: 0, rdm: 0 });
    expect(scoreAt(match, 5400)).toEqual(match.meta.score);
    expect(teamCardsAt(match, "azc", 3058).reds).toBe(1);
    expect(teamCardsAt(match, "azc", 3057).reds).toBe(0);
    expect(goalsAndAssistsAt(match, "azc_09", 5400).goals).toBe(2);
  });

  it("reads ratings from the file: 6.0 at kickoff, the last rating_after at full time", () => {
    expect(ratingAt(match, "azc_09", 0)).toBe(6);
    const log = match.ratingLog.get("azc_09")!;
    expect(ratingAt(match, "azc_09", 5400)).toBe(log[log.length - 1].rating_after);
    expect(log.every((r) => r.delta !== 0)).toBe(true);
  });

  it("interpolates positions in meters inside the pitch", () => {
    const track = match.tracks.get("azc_09")!;
    const [x0, y0] = positionAt(track, 100, match.seconds);
    const [x1, y1] = positionAt(track, 101, match.seconds);
    const [xm, ym] = positionAt(track, 100.5, match.seconds);
    expect(xm).toBeCloseTo((x0 + x1) / 2, 5);
    expect(ym).toBeCloseTo((y0 + y1) / 2, 5);
    for (const id of match.playerIds) {
      const tr = match.tracks.get(id)!;
      for (let s = 0; s < match.seconds; s += 97) {
        const [x, y] = positionAt(tr, s, match.seconds);
        expect(x).toBeGreaterThanOrEqual(0);
        expect(x).toBeLessThanOrEqual(105);
        expect(y).toBeGreaterThanOrEqual(0);
        expect(y).toBeLessThanOrEqual(68);
      }
    }
  });

  it("finds when the sent-off player stops at the touchline", () => {
    const off = match.sentOff.get("azc_06")!;
    expect(off.cardT).toBe(3058);
    expect(off.stopT).toBeGreaterThan(off.cardT);
    const [, y] = positionAt(match.tracks.get("azc_06")!, off.stopT, match.seconds);
    expect(y).toBeCloseTo(68, 0);
  });
});

describe("title race", () => {
  it("needs an Azure win: a draw or a loss leaves Redmond champions", () => {
    expect(titleWinner(STANDINGS, { azc: 3, rdm: 2 })).toBe("azc");
    expect(titleWinner(STANDINGS, { azc: 1, rdm: 1 })).toBe("rdm");
    expect(titleWinner(STANDINGS, { azc: 0, rdm: 1 })).toBe("rdm");
  });
});

describe("sent-off fade without a sent_off activity", () => {
  it("still finds when the player stops instead of waiting for the final second", () => {
    const m = loadFixture();
    const meta = { ...m.meta, activities: m.meta.activities.map((a) => (a === "sent_off" ? "renamed" : a)) } as typeof m.meta;
    const events = { match_id: m.id, events: [...m.eventById.values()] };
    const ratings = { match_id: m.id, entries: [] };
    const positions = {
      match_id: m.id,
      hz: 1 as const,
      unit: "dm" as const,
      seconds: m.seconds,
      entities: meta.entity_order.map((id) => {
        const tr = m.tracks.get(id)!;
        return { id, xy: [...tr.xy], act: tr.act ? [...tr.act] : null };
      }),
    };
    const rebuilt = buildMatch(meta, events, ratings, positions as never);
    expect(rebuilt.sentOff.get("azc_06")!.stopT).toBe(m.sentOff.get("azc_06")!.stopT);
  });
});

describe("sent-off fade waits for the touchline", () => {
  it("does not stop a player who stands still at midfield right after the card (md27)", () => {
    const m = loadFixture("md27_draw");
    for (const [id, off] of m.sentOff) {
      const [, y] = positionAt(m.tracks.get(id)!, off.stopT, m.seconds);
      expect(y).toBeGreaterThanOrEqual(67);
    }
  });
});

describe("keyboard navigation between players", () => {
  it("moves to the nearest player ahead in the pressed direction", () => {
    const m = loadFixture();
    const t = 495; // 8:15, open play
    const at = (id: string) => positionAt(m.tracks.get(id)!, t, m.seconds);
    const [ox, oy] = at("azc_09");
    const dirs: [number, number][] = [[0, -1], [0, 1], [-1, 0], [1, 0]];
    for (const [dx, dy] of dirs) {
      const next = nearestInDirection(m, "azc_09", m.playerIds, [dx, dy], t);
      if (!next) continue;
      const [x, y] = at(next);
      expect((x - ox) * dx + (y - oy) * dy).toBeGreaterThan(0); // always ahead, never behind
    }
    expect(nearestInDirection(m, "azc_09", ["azc_09"], [1, 0], t)).toBeNull();
  });
});

describe("shot flight", () => {
  const goal = match.goals.find((g) => g.t === 2327)!; // 39' Lima: 8.2 m at 79 km/h

  it("flies the shot's own line, then holds in the net, instead of gliding for a second", () => {
    const f = match.shotFlights.find((s) => s.t === 2327)!;
    expect(f.t1 - f.t).toBeGreaterThan(0.3);
    expect(f.t1 - f.t).toBeLessThan(0.5);
    expect(ballAt(match, 2327)).toEqual(f.from);
    expect(ballAt(match, f.t1)).toEqual(f.to);
    expect(ballAt(match, 2327.7)[0]).toBeCloseTo(105, 1);
    expect(ballAt(match, 2328)[0]).toBeCloseTo(105, 1);
  });

  it("never leaves the pitch and never jumps between 60 fps frames", () => {
    for (const f of match.shotFlights) {
      let prev = ballAt(match, Math.floor(f.t) - 0.5);
      for (let t = Math.floor(f.t) - 0.5; t <= Math.floor(f.t) + 1.5; t += 1 / 60) {
        const [x, y] = ballAt(match, t);
        expect(x).toBeGreaterThanOrEqual(-0.5);
        expect(x).toBeLessThanOrEqual(105.5);
        expect(y).toBeGreaterThanOrEqual(-0.5);
        expect(y).toBeLessThanOrEqual(68.5);
        // even a 130 km/h shot moves 0.6 m a frame; a bigger step would be a jump
        expect(Math.hypot(x - prev[0], y - prev[1])).toBeLessThan(1.5);
        prev = [x, y];
      }
    }
  });

  it("reveals a goal in the score only once the ball has landed", () => {
    const reveal = goalRevealT(match, goal);
    expect(reveal).toBeGreaterThan(goal.t);
    expect(reveal).toBeLessThan(goal.t + 1);
    expect(shownScoreAt(match, goal.t)).toEqual(scoreAt(match, goal.t - 1));
    expect(shownScoreAt(match, reveal)).toEqual(goal.score);
    expect(shownScoreAt(match, 5400)).toEqual(match.meta.score);
    // everything in the goal's second waits for the same landing time; other seconds are unchanged
    expect(shownAt(match, goal.t)).toBe(reveal);
    expect(shownAt(match, goal.t + 1)).toBe(goal.t + 1);
  });
});
