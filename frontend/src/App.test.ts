import { describe, expect, it } from "vitest";
import { hashForRoute, routeFromHash } from "@/App";

describe("project hash routing", () => {
  it("uses the project center as the default route", () => {
    expect(routeFromHash("")).toEqual({ view: "projects" });
    expect(routeFromHash("#projects")).toEqual({ view: "projects" });
  });

  it("routes project details and project-scoped generation", () => {
    expect(routeFromHash("#projects/project-1")).toEqual({ view: "project", projectId: "project-1" });
    expect(routeFromHash("#generate/project/project-1")).toEqual({
      view: "generate",
      projectId: "project-1",
      sessionId: null,
    });
  });

  it("hides the legacy history page while keeping legacy session redirects", () => {
    expect(routeFromHash("#history")).toEqual({ view: "projects" });
    expect(routeFromHash("#generate/legacy-session")).toEqual({
      view: "generate",
      projectId: null,
      sessionId: "legacy-session",
    });
  });
});
