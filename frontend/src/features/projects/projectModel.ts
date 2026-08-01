import type { SessionSummary } from "@/types/history";
import type {
  Project,
  ProjectCardData,
  ProjectUpdate,
  ProjectWorkspace,
} from "@/types/projects";
import {
  createEmptyWorkflow,
  discardRetiredStoryboard,
  estimateNarrationDuration,
  restoreWorkflowFromHistory,
  type VideoWorkflowDraft,
  type WorkflowStage,
} from "@/features/video/workflow";

function recordValue(value: unknown): Record<string, unknown> {
  return value !== null && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : {};
}

function workflowDraft(value: unknown): VideoWorkflowDraft | null {
  const candidate = recordValue(value);
  if (candidate.version !== 1 || typeof candidate.sourceText !== "string") return null;
  const draft = candidate as unknown as VideoWorkflowDraft;
  const defaultResearch = createEmptyWorkflow().research;
  return discardRetiredStoryboard({
    ...draft,
    scriptMode: draft.scriptMode ?? createEmptyWorkflow().scriptMode,
    research: {
      ...defaultResearch,
      ...draft.research,
      status: draft.research?.status ?? (
        draft.research?.mode === "verified" ? "reference_unavailable" : "quick"
      ),
      sourceCount: draft.research?.sourceCount ?? 0,
      sources: draft.research?.sources ?? [],
      warnings: draft.research?.warnings ?? [],
    },
  });
}

function workflowStage(value: string | null): WorkflowStage {
  if (value === "storyboard" || value === "video" || value === "output") {
    return value === "output" ? "video" : value;
  }
  return "script";
}

export function projectSessionId(project: Project): string {
  const legacySessionId = project.settings_json.legacy_session_id;
  return typeof legacySessionId === "string" && legacySessionId ? legacySessionId : project.id;
}

export function buildProjectCards(
  projects: Project[],
  sessions: SessionSummary[],
): ProjectCardData[] {
  const sessionsById = new Map(sessions.map((session) => [session.id, session]));
  return projects.map((project) => {
    const session = sessionsById.get(projectSessionId(project)) ?? sessionsById.get(project.id) ?? null;
    const draft = recordValue(project.settings_json.workspace_draft);
    const draftStoryboardCount = Array.isArray(draft.storyboard) ? draft.storyboard.length : 0;
    const historyStoryboardCount = Number(session?.metadata.n_frames ?? 0);
    const hasSavedDraft = Boolean(project.settings_json.workspace_draft);
    const storyboardCount = hasSavedDraft
      ? draftStoryboardCount
      : Number.isFinite(historyStoryboardCount) ? historyStoryboardCount : 0;
    const currentOutputIsValid = project.status === "completed" && project.current_stage === "output";
    return {
      ...project,
      storyboardCount,
      latestJobStatus: currentOutputIsValid ? session?.status ?? null : null,
      latestJobId: currentOutputIsValid ? session?.latest_job_id ?? null : null,
      thumbnailUrl: currentOutputIsValid ? project.thumbnail_path ?? session?.thumbnail_url ?? null : null,
      videoUrl: currentOutputIsValid ? session?.video_url ?? null : null,
      session,
    };
  });
}

export function restoreProjectWorkflow(
  workspace: ProjectWorkspace,
  localDraft: VideoWorkflowDraft | null,
): VideoWorkflowDraft {
  const activeResearchId = typeof workspace.project.settings_json.active_research_job_id === "string"
    ? workspace.project.settings_json.active_research_job_id
    : null;
  const withResearchReference = (draft: VideoWorkflowDraft): VideoWorkflowDraft => discardRetiredStoryboard({
    ...draft,
    sessionId: workspace.project.id,
    storyboard: draft.storyboard.map((scene) => ({
      ...scene,
      estimatedDuration: scene.estimatedDuration > 1
        ? scene.estimatedDuration
        : estimateNarrationDuration(scene.narration),
    })),
    research: {
      ...draft.research,
      activeJobId: activeResearchId ?? draft.research.activeJobId,
    },
  });
  const savedDraft = workflowDraft(workspace.project.settings_json.workspace_draft);
  if (savedDraft) return withResearchReference(savedDraft);

  if (workspace.history) {
    return withResearchReference(restoreWorkflowFromHistory(workspace.history));
  }

  if (localDraft) return withResearchReference(localDraft);

  return withResearchReference({
    ...createEmptyWorkflow(workspace.project.id),
    title: workspace.project.title,
    sourceText: workspace.project.source_text ?? "",
    stage: workflowStage(workspace.project.current_stage),
  });
}

export function buildProjectDraftUpdate(
  project: Project,
  draft: VideoWorkflowDraft,
  updatedAt = new Date().toISOString(),
  hasCompletedVideo = false,
): ProjectUpdate {
  const videoCompleted = hasCompletedVideo;
  return {
    title: draft.title.trim() || project.title,
    source_text: draft.sourceText,
    current_stage: videoCompleted ? "output" : draft.stage,
    status: project.status === "archived" ? "archived" : videoCompleted ? "completed" : "active",
    settings_json: {
      workspace_draft: { ...draft, sessionId: project.id },
      workspace_draft_updated_at: updatedAt,
    },
  };
}
