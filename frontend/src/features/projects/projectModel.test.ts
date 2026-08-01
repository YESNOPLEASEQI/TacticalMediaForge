import { describe, expect, it } from "vitest";
import type { SessionDetail, SessionSummary } from "@/types/history";
import type { Project } from "@/types/projects";
import {
  buildProjectCards,
  buildProjectDraftUpdate,
  restoreProjectWorkflow,
} from "@/features/projects/projectModel";
import { createEmptyWorkflow } from "@/features/video/workflow";

const project: Project = {
  id: "project-1",
  title: "雷达项目",
  description: null,
  project_type: "video_agent",
  status: "active",
  current_stage: "storyboard",
  source_text: "数据库来源",
  thumbnail_path: null,
  owner_id: null,
  settings_json: { legacy_session_id: "legacy-session" },
  created_at: "2026-07-14T00:00:00Z",
  updated_at: "2026-07-14T01:00:00Z",
  archived_at: null,
  deleted_at: null,
};

const session: SessionSummary = {
  id: "legacy-session",
  title: "历史标题",
  project_type: "video_agent",
  status: "success",
  job_count: 2,
  latest_job_id: "job-2",
  video_url: "/api/files/final.mp4",
  metadata: { n_frames: 6 },
};

describe("project model", () => {
  it("enriches database projects with compatible session summaries", () => {
    const cards = buildProjectCards([{
      ...project,
      status: "completed",
      current_stage: "output",
    }], [session]);

    expect(cards[0]).toMatchObject({
      id: "project-1",
      storyboardCount: 6,
      latestJobStatus: "success",
      videoUrl: "/api/files/final.mp4",
    });
  });

  it("restores the database workspace draft before history and localStorage", () => {
    const databaseDraft = {
      ...createEmptyWorkflow("project-1"),
      title: "数据库草稿",
      sourceText: "正式数据",
    };
    const localDraft = { ...databaseDraft, title: "本地草稿" };
    const detail = {
      session,
      messages: [],
      generation_jobs: [],
      assets: [],
      workflow_snapshots: [],
    } satisfies SessionDetail;

    const restored = restoreProjectWorkflow(
      { project: { ...project, settings_json: { workspace_draft: databaseDraft } }, history: detail },
      localDraft,
    );

    expect(restored.title).toBe("数据库草稿");
    expect(restored.sessionId).toBe("project-1");
  });

  it("discards a retired storyboard while preserving its narrations", () => {
    const draft = {
      ...createEmptyWorkflow("project-1"),
      stage: "video" as const,
      narrations: ["kept narration"],
      scriptConfirmed: true,
      storyboardConfirmed: true,
      storyboard: [{
        id: "scene-0",
        index: 0,
        narration: "kept narration",
        visualDescription: "A non-identifying main battle tank",
        mediaPrompt: "A non-identifying main battle tank",
        estimatedDuration: 5,
        assetType: "video" as const,
        status: "draft" as const,
      }],
    };

    const restored = restoreProjectWorkflow(
      { project: { ...project, settings_json: { workspace_draft: draft } }, history: null },
      null,
    );

    expect(restored.narrations).toEqual(["kept narration"]);
    expect(restored.storyboard).toEqual([]);
    expect(restored.storyboardConfirmed).toBe(false);
    expect(restored.stage).toBe("storyboard");
  });

  it("repairs legacy storyboard durations defaulted to one second", () => {
    const draft = {
      ...createEmptyWorkflow("project-1"),
      storyboard: [{
        id: "scene-0",
        index: 0,
        narration: "12345678901234567890",
        visualDescription: "documentary shot",
        mediaPrompt: "documentary shot",
        estimatedDuration: 1,
        assetType: "video" as const,
        status: "draft" as const,
      }],
    };

    const restored = restoreProjectWorkflow(
      { project: { ...project, settings_json: { workspace_draft: draft } }, history: null },
      null,
    );

    expect(restored.storyboard[0].estimatedDuration).toBe(5);
  });

  it("serializes a project draft into the existing PATCH contract", () => {
    const draft = {
      ...createEmptyWorkflow("project-1"),
      title: "新标题",
      sourceText: "新脚本",
      stage: "storyboard" as const,
    };

    expect(buildProjectDraftUpdate(project, draft, "2026-07-14T02:00:00Z")).toEqual({
      title: "新标题",
      source_text: "新脚本",
      current_stage: "storyboard",
      status: "active",
      settings_json: {
        workspace_draft: draft,
        workspace_draft_updated_at: "2026-07-14T02:00:00Z",
      },
    });
  });

  it("does not overwrite a completed video project with an active draft status", () => {
    const draft = {
      ...createEmptyWorkflow("project-1"),
      stage: "video" as const,
    };

    expect(buildProjectDraftUpdate(project, draft, "2026-07-14T02:00:00Z", true)).toMatchObject({
      current_stage: "output",
      status: "completed",
    });
  });

  it("invalidates an old completed output after the current draft changes", () => {
    const draft = {
      ...createEmptyWorkflow("project-1"),
      stage: "storyboard" as const,
      contentRevision: 4,
      submittedRevision: 1,
    };
    const completedProject = { ...project, status: "completed", current_stage: "output" };

    expect(buildProjectDraftUpdate(completedProject, draft, "2026-07-14T02:00:00Z", false)).toMatchObject({
      current_stage: "storyboard",
      status: "active",
    });
  });

  it("restores the active research job reference from project settings", () => {
    const restored = restoreProjectWorkflow(
      {
        project: {
          ...project,
          settings_json: { active_research_job_id: "research-7" },
        },
        history: null,
      },
      null,
    );

    expect(restored.research.activeJobId).toBe("research-7");
  });
});
