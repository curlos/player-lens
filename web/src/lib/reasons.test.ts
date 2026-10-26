import { describe, expect, it } from "vitest";
import { REASON_CODES, reasonText } from "./reasons";

const nameOf = (id: string) => (id === "rdm_06" ? "#6 L. Weber" : "");

describe("reason templates", () => {
  it("covers the 34 codes in specs/frontend.md", () => {
    expect(REASON_CODES).toHaveLength(34);
  });

  it("fills values in English and Spanish", () => {
    expect(reasonText("pressure_regain", { opponent: "rdm_06" }, "en", nameOf)).toBe("Pressed #6 L. Weber and the team won the ball back");
    expect(reasonText("goal", { xg: 0.127 }, "en", nameOf)).toBe("Scored (xG 0.13)");
    expect(reasonText("recovery_run", { distance_m: 22.4 }, "es", nameOf)).toBe("Sprint de 22 m para replegar");
  });

  it("never fails or prints 'undefined' when values are missing", () => {
    for (const lang of ["en", "es"] as const) {
      for (const code of REASON_CODES) {
        const text = reasonText(code, undefined, lang, nameOf);
        expect(text).not.toMatch(/undefined|NaN|\{/);
      }
    }
  });

  it("falls back to the code for unknown codes, including Object.prototype names", () => {
    expect(reasonText("constructor", {}, "en", nameOf)).toBe("constructor");
    expect(reasonText("new_code", {}, "es", nameOf)).toBe("new code");
  });

  it("keeps shape_no_change silent", () => {
    expect(reasonText("shape_no_change", { deviation_m: 2 }, "en", nameOf)).toBe("");
  });
});
