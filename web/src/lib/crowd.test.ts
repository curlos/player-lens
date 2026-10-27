import { describe, expect, it } from "vitest";
import { CROWD, CROWD_CLIPS } from "./config";
import { crowdCues, murmurLevel } from "./crowd";
import { goalRevealT } from "./match";
import { loadFixture } from "./testData";

const match = loadFixture();
const goalAt = (t: number) => match.goals.find((g) => g.t === t)!;

/** Plays the clock through [from, to] at `rate` in 60 fps steps, as the App's frame listener does. */
function playThrough(from: number, to: number, rate = 1) {
  const step = rate / 60;
  const cues = [];
  for (let t = from; t < to; t += step) cues.push(...crowdCues(match, t, Math.min(t + step, to), rate));
  return cues;
}

describe("crowd director (hero md38_title_decider)", () => {
  it("roars for Azure's 39' goal when the ball lands, not at the kick", () => {
    const reveal = goalRevealT(match, goalAt(2327));
    expect(crowdCues(match, 2326, 2327.05, 1).some((c) => c.sound === "roar")).toBe(false);
    const roar = playThrough(2326, 2329).find((c) => c.sound === "roar")!;
    expect(roar.t).toBe(reveal);
    expect(roar.gain).toBe(CROWD.goalHome);
  });

  it("groans, then hushes the home crowd, for Redmond's 12' goal", () => {
    const cues = playThrough(714, 717);
    expect(cues.map((c) => c.sound)).toEqual(["conceded"]);
    expect(cues[0].gain).toBe(CROWD.goalAway);
    const reveal = goalRevealT(match, match.goals.find((g) => g.t >= 714 && g.t <= 717)!);
    const before = murmurLevel(match, reveal - 0.01);
    expect(murmurLevel(match, reveal + 1)).toBeLessThan(before * (CROWD.goalAwayHush + 0.05));
    expect(murmurLevel(match, reveal + CROWD.goalAwayHushS + 0.5)).toBeGreaterThanOrEqual(CROWD.murmurBase);
  });

  it("boos the 51' red card against Azure once, with one whistle, and ignores the merged second yellow", () => {
    const cues = crowdCues(match, 3057.5, 3058 + CROWD.afterWhistleS, 1);
    const whistles = cues.filter((c) => c.sound === "whistle");
    expect(whistles).toHaveLength(1);
    expect(whistles[0].gain).toBe(CROWD.whistle);
    const boos = cues.filter((c) => c.sound === "boo");
    expect(boos).toHaveLength(1);
    expect(boos[0].gain).toBe(CROWD.red);
    expect(boos[0].play).toBe(CROWD.redPlay);
    expect(boos[0].t).toBe(whistles[0].t + CROWD.afterWhistleS); // the crowd answers the whistle
  });

  it("cheers Azure's 54' penalty award", () => {
    expect(crowdCues(match, 3226.5, 3227 + CROWD.afterWhistleS, 1).map((c) => c.sound)).toEqual(["whistle", "cheer"]);
  });

  it("at 30x reacts only to goals and red cards, but still whistles every card and the penalty", () => {
    const cues = playThrough(0, 5400, 30);
    const type = (c: { source: string }) => match.eventById.get(c.source)?.type ?? c.source;
    const crowd = new Set(cues.filter((c) => c.sound !== "whistle" && c.sound !== "whistleLong").map(type));
    expect([...crowd].sort()).toEqual(["card_red", "goal"]);
    const whistled = new Set(cues.filter((c) => c.sound === "whistle").map(type));
    expect([...whistled].sort()).toEqual(["card_red", "card_yellow", "penalty"]);
    const decisions = match.events.filter((e) => e.type === "card_yellow" || e.type === "card_red" || e.type === "penalty");
    for (const e of decisions) expect(cues.some((c) => c.sound === "whistle" && c.t === e.t)).toBe(true);
  });

  it("shortens reactions with the speed, never below the minimum", () => {
    const roarAt = (rate: number) => playThrough(2326, 2330, rate).find((c) => c.sound === "roar")!.play;
    expect(roarAt(1)).toBeUndefined(); // the clip's own 1x length
    expect(roarAt(2)).toBe(CROWD_CLIPS.roar.play / 2);
    expect(roarAt(4)).toBe(CROWD_CLIPS.roar.play / 4);
    expect(roarAt(30)).toBe(CROWD.minFastPlayS);
  });

  it("plays every goal exactly once over a full match at 1x, plus one final whistle", () => {
    const cues = playThrough(0, 5400);
    const goalCues = cues.filter((c) => match.eventById.get(c.source)?.type === "goal");
    expect(goalCues).toHaveLength(match.goals.length);
    expect(cues.filter((c) => c.sound === "whistleLong")).toHaveLength(1);
  });

  it("whistles only for kickoffs, cards, the penalty and full time, never a plain foul or offside", () => {
    const types = new Set(
      playThrough(0, 5400)
        .filter((c) => c.sound === "whistle" || c.sound === "whistleLong")
        .map((c) => match.eventById.get(c.source)?.type ?? c.source),
    );
    expect([...types].sort()).toEqual(["card_red", "card_yellow", "full_time", "kickoff", "penalty"]);
  });

  it("is deterministic", () => {
    expect(crowdCues(match, 3000, 3300, 1)).toEqual(crowdCues(match, 3000, 3300, 1));
  });

  it("keeps the murmur between its hushed base and its loudest swell, silent after full time", () => {
    for (let t = 0; t < 5400; t += 7) {
      const m = murmurLevel(match, t);
      expect(m).toBeGreaterThanOrEqual(CROWD.murmurBase * CROWD.goalAwayHush);
      expect(m).toBeLessThanOrEqual(CROWD.murmurBase + Math.max(CROWD.murmurHomeAttack, CROWD.murmurAwayAttack));
    }
    expect(murmurLevel(match, 5400)).toBe(0);
  });
});
