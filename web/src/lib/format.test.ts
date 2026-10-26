import { describe, expect, it } from "vitest";
import { deltaColor, ratingBand } from "./colors";
import { clockLabel, deltaLabel, lastIndexAtOrBefore, minuteLabel, ratingLabel } from "./format";

describe("format", () => {
  it("uses the football minute floor(t / 60) + 1", () => {
    expect(minuteLabel(0)).toBe("1'");
    expect(minuteLabel(87 * 60 + 12)).toBe("88'");
  });

  it("shows the clock as mm:ss and ends at 90:00", () => {
    expect(clockLabel(0)).toBe("00:00");
    expect(clockLabel(2327.6)).toBe("38:47");
    expect(clockLabel(5400)).toBe("90:00");
  });

  it("keeps ratings in the 3.1 to 9.9 display range with one decimal", () => {
    expect(ratingLabel(6)).toBe("6.0");
    expect(ratingLabel(8.88)).toBe("8.9");
    expect(ratingLabel(10.2)).toBe("9.9");
    expect(ratingLabel(2.5)).toBe("3.1");
  });

  it("signs deltas with two decimals", () => {
    expect(deltaLabel(0.1)).toBe("+0.10");
    expect(deltaLabel(-0.05)).toBe("-0.05");
  });

  it("maps ratings to the five color bands on the displayed value", () => {
    expect([4.9, 5.0, 5.96, 6.94, 7.0, 7.96, 8.0].map(ratingBand)).toEqual([0, 1, 2, 2, 3, 4, 4]);
  });

  it("binary-searches the last item at or before t", () => {
    const items = [{ t: 1 }, { t: 5 }, { t: 5 }, { t: 9 }];
    expect(lastIndexAtOrBefore(items, 0)).toBe(-1);
    expect(lastIndexAtOrBefore(items, 5)).toBe(2);
    expect(lastIndexAtOrBefore(items, 100)).toBe(3);
  });

  it("colours gains and losses green and red, or blue and orange for colorblind viewers", () => {
    expect(deltaColor(0.1, false)).not.toBe(deltaColor(-0.1, false));
    expect(deltaColor(0.1, true)).not.toBe(deltaColor(-0.1, true));
    // colorblind mode never uses the red/green pair
    expect([deltaColor(0.1, true), deltaColor(-0.1, true)]).not.toContain(deltaColor(0.1, false));
    expect([deltaColor(0.1, true), deltaColor(-0.1, true)]).not.toContain(deltaColor(-0.1, false));
  });
});
