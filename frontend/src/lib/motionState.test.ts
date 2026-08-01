import { describe, expect, it } from "vitest";
import { didSemanticValueChange, newIds } from "@/lib/motionState";

describe("motion state helpers", () => {
  it("returns only IDs that have not been seen", () => {
    expect(newIds(new Set(["a"]), ["a", "b"])).toEqual(["b"]);
    expect(newIds(new Set(["a", "b"]), ["a", "b"])).toEqual([]);
  });

  it("reports semantic changes after an initial value exists", () => {
    expect(didSemanticValueChange(undefined, "pending")).toBe(false);
    expect(didSemanticValueChange("running", "running")).toBe(false);
    expect(didSemanticValueChange("pending", "running")).toBe(true);
  });
});
