import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { Clock } from "./clock";

describe("clock", () => {
  beforeEach(() => {
    vi.stubGlobal("requestAnimationFrame", () => 1);
    vi.stubGlobal("cancelAnimationFrame", () => {});
  });
  afterEach(() => vi.unstubAllGlobals());

  it("restarting from full time is a seek: t goes to 0, seek listeners and frames fire", () => {
    const clock = new Clock(5400);
    clock.seek(5400);
    const seeks = clock.getState().seekCount;
    const frames: number[] = [];
    clock.subscribeFrame((t) => frames.push(t));
    clock.play();
    expect(clock.t).toBe(0);
    expect(clock.getState().seekCount).toBe(seeks + 1);
    expect(clock.getState().playing).toBe(true);
    expect(frames[frames.length - 1]).toBe(0);
  });
});
