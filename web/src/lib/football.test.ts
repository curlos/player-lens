import { describe, expect, it } from "vitest";
import { footballPatches } from "./football";

describe("football pattern", () => {
  it("has a centre patch and five edge patches", () => {
    expect(footballPatches(1)).toHaveLength(6);
  });
});
