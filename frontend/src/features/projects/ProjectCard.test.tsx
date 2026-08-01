import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ProjectCard } from "@/features/projects/ProjectCard";
import type { ProjectCardData } from "@/types/projects";

const project: ProjectCardData = { id: "project-a", title: "预警体系", description: null, project_type: "video_agent", status: "active", current_stage: "storyboard", source_text: "source", thumbnail_path: null, owner_id: null, settings_json: {}, created_at: "2026-07-14T00:00:00Z", updated_at: "2026-07-14T01:00:00Z", archived_at: null, deleted_at: null, storyboardCount: 4, latestJobStatus: "running", latestJobId: "job-a", thumbnailUrl: null, videoUrl: null, session: null };

describe("project card actions", () => {
  it("moves secondary actions into a three-dot menu", () => {
    render(<ProjectCard project={project} onArchive={vi.fn()} onContinue={vi.fn()} onDelete={vi.fn()} onOpen={vi.fn()} onRename={vi.fn()} />);
    expect(screen.queryByText("当前阶段")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /重命名/ })).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "更多项目操作" }));
    expect(screen.getByRole("button", { name: "重命名" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "归档" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "删除" })).toBeInTheDocument();
  });

  it("exposes stable motion identity without changing card semantics", () => {
    render(<ProjectCard project={project} onArchive={vi.fn()} onContinue={vi.fn()} onDelete={vi.fn()} onOpen={vi.fn()} onRename={vi.fn()} />);
    const card = screen.getByRole("article");
    expect(card).toHaveAttribute("data-project-id", project.id);
    expect(card).toHaveAttribute("data-motion", "project-card");
  });

  it("supports project selection for batch actions", () => {
    const onSelectedChange = vi.fn();
    render(<ProjectCard project={project} selected onSelectedChange={onSelectedChange} onArchive={vi.fn()} onContinue={vi.fn()} onDelete={vi.fn()} onOpen={vi.fn()} onRename={vi.fn()} />);

    const selector = screen.getByRole("checkbox", { name: `选择项目 ${project.title}` });
    expect(selector).toBeChecked();
    fireEvent.click(selector);
    expect(onSelectedChange).toHaveBeenCalledWith(project.id, false);
  });
});
