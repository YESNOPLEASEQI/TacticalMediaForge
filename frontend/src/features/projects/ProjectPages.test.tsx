import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ProjectCenterPage } from "@/features/projects/ProjectCenterPage";
import { ProjectDetailPage } from "@/features/projects/ProjectDetailPage";

afterEach(() => vi.unstubAllGlobals());

function response(payload: unknown) {
  return new Response(JSON.stringify(payload), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  });
}

function renderPage(node: React.ReactNode) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}>{node}</QueryClientProvider>);
}

const project = {
  id: "project-1",
  title: "高超声速预警体系",
  description: "第一版项目",
  project_type: "video_agent",
  status: "active",
  current_stage: "storyboard",
  source_text: "source",
  thumbnail_path: null,
  owner_id: null,
  settings_json: {},
  created_at: "2026-07-14T00:00:00Z",
  updated_at: "2026-07-14T01:00:00Z",
  archived_at: null,
  deleted_at: null,
};

const sessionDetail = {
  session: {
    id: "project-1",
    title: project.title,
    project_type: "video_agent",
    status: "success",
    job_count: 1,
    latest_job_id: "job-1",
    video_url: "/api/files/final.mp4",
    metadata: { n_frames: 3 },
  },
  messages: [],
  generation_jobs: [],
  assets: [],
  workflow_snapshots: [],
};

describe("project pages", () => {
  it("renders the project center from project and compatible history APIs", async () => {
    vi.stubGlobal("fetch", vi.fn()
      .mockResolvedValueOnce(response([project]))
      .mockResolvedValueOnce(response({ sessions: [sessionDetail.session], total: 1 })));

    renderPage(<ProjectCenterPage onContinue={() => undefined} onOpenProject={() => undefined} />);

    expect(await screen.findByRole("heading", { name: "项目中心" })).toBeInTheDocument();
    expect(await screen.findByText("高超声速预警体系")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /新建项目/ })).toBeInTheDocument();
  });

  it("opens a newly created project directly in script creation", async () => {
    const onContinue = vi.fn();
    const onOpenProject = vi.fn();
    const createdProject = {
      ...project,
      id: "new-project",
      title: "New project",
      status: "draft",
      current_stage: "script",
    };
    vi.stubGlobal("fetch", vi.fn().mockImplementation((input: RequestInfo | URL, init?: RequestInit) => {
      if (init?.method === "POST") return Promise.resolve(response(createdProject));
      if (String(input).includes("/api/sessions")) {
        return Promise.resolve(response({ sessions: [], total: 0 }));
      }
      return Promise.resolve(response([]));
    }));

    const view = renderPage(<ProjectCenterPage onContinue={onContinue} onOpenProject={onOpenProject} />);
    fireEvent.click(await screen.findByRole("button", { name: /新建项目/ }));

    const titleInput = view.container.querySelector<HTMLInputElement>("#new-project-title");
    const form = titleInput?.closest("form");
    expect(titleInput).not.toBeNull();
    expect(form).not.toBeNull();
    fireEvent.change(titleInput!, { target: { value: "New project" } });
    fireEvent.submit(form!);

    await waitFor(() => expect(onContinue).toHaveBeenCalledWith("new-project"));
    expect(onOpenProject).not.toHaveBeenCalled();
  });

  it("renders project detail tabs and database-backed overview", async () => {
    vi.stubGlobal("fetch", vi.fn()
      .mockResolvedValueOnce(response(project))
      .mockResolvedValueOnce(response(sessionDetail)));

    renderPage(<ProjectDetailPage onBack={() => undefined} onContinue={() => undefined} projectId="project-1" />);

    expect(await screen.findByRole("heading", { name: "高超声速预警体系" })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "概览" })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "脚本" })).toBeInTheDocument();
    expect(await screen.findByRole("tabpanel")).toHaveAttribute("data-project-tab", "overview");
    expect(screen.getByRole("button", { name: /继续创作/ })).toBeInTheDocument();
  });

  it("keeps archived projects out of all projects and supports batch archive", async () => {
    const activeProject = { ...project, id: "active-project", title: "当前项目" };
    const archivedProject = { ...project, id: "archived-project", title: "已封存项目", status: "archived", archived_at: "2026-07-15T00:00:00Z" };
    const fetchMock = vi.fn().mockImplementation((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (init?.method === "PATCH") return Promise.resolve(response({ ...activeProject, status: "archived" }));
      if (url.includes("/api/sessions")) return Promise.resolve(response({ sessions: [], total: 0 }));
      return Promise.resolve(response([activeProject, archivedProject]));
    });
    vi.stubGlobal("fetch", fetchMock);

    renderPage(<ProjectCenterPage onContinue={() => undefined} onOpenProject={() => undefined} />);

    expect(await screen.findByText("当前项目")).toBeInTheDocument();
    expect(screen.queryByText("已封存项目")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("checkbox", { name: "选择当前列表" }));
    fireEvent.click(screen.getByRole("button", { name: /批量归档/ }));

    await waitFor(() => expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/api/projects/active-project"),
      expect.objectContaining({ method: "PATCH" }),
    ));
  });
});
