import { afterEach, describe, expect, it, vi } from "vitest";
import { createProject, deleteProject, getProjectWorkspace, updateProject } from "@/api/projects";

afterEach(() => vi.unstubAllGlobals());

function jsonResponse(payload: unknown, status = 200) {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

describe("project api", () => {
  it("uses the real CRUD endpoints", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse({ id: "project-1", title: "新项目" }, 201))
      .mockResolvedValueOnce(jsonResponse({ id: "project-1", title: "重命名" }))
      .mockResolvedValueOnce(new Response(null, { status: 204 }));
    vi.stubGlobal("fetch", fetchMock);

    await createProject({ title: "新项目" });
    await updateProject("project-1", { title: "重命名" });
    await deleteProject("project-1");

    expect(fetchMock.mock.calls.map(([url, init]) => [url, init?.method])).toEqual([
      ["/api/projects", "POST"],
      ["/api/projects/project-1", "PATCH"],
      ["/api/projects/project-1", "DELETE"],
    ]);
  });

  it("loads project detail and treats a missing compatible session as an empty history", async () => {
    const project = {
      id: "project-1",
      title: "草稿",
      settings_json: {},
    };
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValueOnce(jsonResponse(project))
        .mockResolvedValueOnce(jsonResponse({ detail: "not found" }, 404)),
    );

    const workspace = await getProjectWorkspace("project-1");

    expect(workspace.project.id).toBe("project-1");
    expect(workspace.history).toBeNull();
  });
});
